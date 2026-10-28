using System;
using System.Collections.Generic;
using System.Text;
using Draygo.API;
using Sandbox.Definitions;
using Sandbox.Game.Entities;
using Sandbox.ModAPI;
using VRage.Game;
using VRage.Game.Components;
using VRage.Game.Entity;
using VRage.Game.ModAPI;
using VRage.Utils;
using VRageMath;
using BlendTypeEnum = VRageRender.MyBillboard.BlendTypeEnum;

namespace ArcanePower
{
    // Follows SCF BuildPreviewHud's native builder, facing/rotation arrows and
    // optional Text HUD API pattern. All checks are advisory and client-only.
    [MySessionComponentDescriptor(MyUpdateOrder.AfterSimulation)]
    public sealed partial class ThermalBuildGuide : MySessionComponentBase
    {
        private readonly StringBuilder text = new StringBuilder();
        private readonly List<IMySlimBlock> blocks = new List<IMySlimBlock>();
        private readonly List<ThermalEndpoint> nodes = new List<ThermalEndpoint>();
        private readonly Dictionary<long, IMyCubeGrid> assemblyGrids = new Dictionary<long, IMyCubeGrid>();
        // Square is opaque white; SquareFullColor bakes in grey-blue tint/alpha.
        private readonly MyStringId lineMaterial = MyStringId.GetOrCompute("Square");
        private readonly MyStringId greenArrow = MyStringId.GetOrCompute("ArcaneThermal_ArrowGreen");
        private readonly MyStringId redArrow = MyStringId.GetOrCompute("ArcaneThermal_ArrowRed");
        private readonly MyStringId blueArrow = MyStringId.GetOrCompute("ArcaneThermal_ArrowBlue");
        private readonly MyStringId leftArrow = MyStringId.GetOrCompute("ArcaneThermal_TurnLeft");
        private readonly MyStringId rightArrow = MyStringId.GetOrCompute("ArcaneThermal_TurnRight");
        private HudAPIv2 api;
        private HudAPIv2.HUDMessage panel;
        private IMyHudNotification fallback;
        private IMyCubeGrid grid;
        private ThermalEndpoint selected;
        private ThermalBuildCheck check;
        private Matrix rotation, suggested;
        private Vector3 centre;
        private Vector3D previewWorld;
        private bool preview, fullHud, active, loggedError;
        private bool radiatorGuide, radiatorAligned;
        private MatrixD radiatorFrame;
        private Vector3D radiatorDock;
        private int tick;
        private string fallbackText;
        private const string GuideCommand = "/ap guide";
        private const string GuidePreferenceFile = "construction-guide.txt";
        private bool guideEnabled = true, chatSubscribed;

        private void LoadPreference()
        {
            try
            {
                if (!MyAPIGateway.Utilities.FileExistsInLocalStorage(GuidePreferenceFile, typeof(ThermalBuildGuide))) return;
                using (var reader = MyAPIGateway.Utilities.ReadFileInLocalStorage(GuidePreferenceFile, typeof(ThermalBuildGuide)))
                {
                    bool saved;
                    if (bool.TryParse(reader.ReadToEnd().Trim(), out saved)) guideEnabled = saved;
                }
            }
            catch (Exception error) { Log(error); }
        }

        private void GuideChat(string message, ref bool sendToOthers)
        {
            if (!string.Equals(message.Trim(), GuideCommand, StringComparison.OrdinalIgnoreCase)) return;
            sendToOthers = false;
            guideEnabled = !guideEnabled;
            Hide();
            string persistence = " Saved for future sessions.";
            try
            {
                using (var writer = MyAPIGateway.Utilities.WriteFileInLocalStorage(GuidePreferenceFile, typeof(ThermalBuildGuide)))
                    writer.Write(guideEnabled);
            }
            catch (Exception error)
            {
                Log(error);
                persistence = " Could not save this preference; it applies only this session.";
            }
            MyAPIGateway.Utilities.ShowMessage("Arcane Power", "Construction guide " + (guideEnabled ? "on." : "off.")
                + persistence + " Type " + GuideCommand + " to toggle it again.");
        }

        public override void LoadData()
        {
            if (MyAPIGateway.Utilities.IsDedicated) return;
            LoadPreference();
            MyAPIGateway.Utilities.MessageEntered += GuideChat;
            chatSubscribed = true;
            api = new HudAPIv2(() => panel = new HudAPIv2.HUDMessage(text, new Vector2D(-.97, .48),
                null, -1, .72, true, true) { Visible = false });
        }

        public override void UpdateAfterSimulation()
        {
            if (MyAPIGateway.Utilities.IsDedicated) return;
            if (!Visible()) { Hide(); return; }
            if (++tick % 6 != 0) return;
            try { Refresh(); }
            catch (Exception error) { Hide(); Log(error); }
        }

        private bool Visible()
        {
            return guideEnabled && MyAPIGateway.Session != null && MyAPIGateway.Session.Player != null
                && MyAPIGateway.Session.Camera != null && MyAPIGateway.Session.Config.HudState != 0
                && !MyAPIGateway.Gui.IsCursorVisible && !MyAPIGateway.Gui.ChatEntryVisible;
        }

        private void Refresh()
        {
            Hide();
            fullHud = MyAPIGateway.Session.Config.HudState == 1;
            var builder = MyCubeBuilder.Static;
            var definition = builder == null || builder.CubeBuilderState == null ? null : builder.CubeBuilderState.CurrentBlockDefinition;
            preview = builder != null && builder.IsActivated && builder.BlockCreationIsActivated && definition != null;
            // Keep the vessel's mounting guide visible while placing its hardware.
            // Resolve the aimed vessel below and retain the normal access check.
            if (preview && ReactorHardware(definition.Id.SubtypeName)) preview = false;
            ThermalModel model;
            IMySlimBlock aimed = null;
            if (preview)
            {
                if (!ThermalModels.All.TryGetValue(definition.Id.SubtypeName, out model)) return;
                if (model.Kind == ThermalKind.Reactor) return;
                var box = builder.GetBuildBoundingBox();
                // GetBuildBoundingBox can replace its centre with the add-cell
                // anchor when aiming at an existing block. Use the model pose,
                // including ModelOffset, for even-sized machines and sockets.
                builder.GetAddPosition(out previewWorld);
                grid = builder.FindClosestGrid();
                if (grid == null)
                { Show(model, "Place on a large grid to inspect connections", null); return; }
                if ((box.HalfExtent - new Vector3D(model.Cells) * 1.25).LengthSquared() > .01)
                { Show(model, "Block definition size differs from the thermal model contract", null); return; }
                MatrixD relative = MatrixD.CreateFromQuaternion(box.Orientation) * grid.WorldMatrixInvScaled;
                rotation = (Matrix)relative.GetOrientation();
                centre = (Vector3)Vector3D.Transform(previewWorld, grid.WorldMatrixInvScaled)
                    + Vector3.TransformNormal(definition.ModelOffset, rotation);
                previewWorld = Vector3D.Transform(centre, grid.WorldMatrix);
            }
            else
            {
                aimed = AssemblyVessel(Aim());
                if (aimed == null || !ThermalModels.All.TryGetValue(aimed.BlockDefinition.Id.SubtypeName, out model)) return;
                var terminal = aimed.FatBlock as IMyTerminalBlock;
                if (terminal != null && !terminal.HasPlayerAccess(MyAPIGateway.Session.Player.IdentityId))
                { Show(model, "Access denied: construction inspection unavailable", null); return; }
                grid = aimed.CubeGrid;
            }
            if (grid.GridSizeEnum != MyCubeSize.Large)
            { Show(model, "Thermal blocks require a 2.5 m large grid", null); return; }
            if (model.Kind == ThermalKind.RadiatorPanel)
            {
                Show(model, RadiatorGuide(model, aimed), null);
                return;
            }

            blocks.Clear(); nodes.Clear();
            assemblyGrids.Clear(); assemblyGrids[grid.EntityId] = grid;
            var rotary = ThermalPipeJoint.Snapshot(MyAPIGateway.Session.Player.IdentityId);
            foreach (long id in ThermalNetwork.ConnectedGrids(grid.EntityId, rotary))
            {
                VRage.ModAPI.IMyEntity entity;
                if (MyAPIGateway.Entities.TryGetEntityById(id, out entity) && entity is IMyCubeGrid)
                    assemblyGrids[id] = (IMyCubeGrid)entity;
            }
            foreach (var member in assemblyGrids.Values)
            {
                var local = new List<IMySlimBlock>();
                member.GetBlocks(local, b => ThermalModels.All.ContainsKey(b.BlockDefinition.Id.SubtypeName));
                blocks.AddRange(local);
            }
            for (int i = 0; i < blocks.Count; i++)
            {
                var block = blocks[i];
                var spec = ThermalModels.All[block.BlockDefinition.Id.SubtypeName];
                Matrix orientation;
                block.Orientation.GetMatrix(out orientation);
                Vector3 at = block.FatBlock == null ? (Vector3)(block.Min + block.Max) * (block.CubeGrid.GridSize * .5f)
                    + Vector3.TransformNormal(((MyCubeBlockDefinition)block.BlockDefinition).ModelOffset, orientation)
                    : ((MyEntity)block.FatBlock).PositionComp.LocalMatrixRef.Translation;
                var terminal = block.FatBlock as IMyTerminalBlock;
                bool healthy = block.CubeGrid.Physics != null && block.BuildLevelRatio >= 1
                    && block.FatBlock != null && block.FatBlock.IsFunctional
                    && (terminal == null || terminal.HasPlayerAccess(MyAPIGateway.Session.Player.IdentityId))
                    && (spec.Kind == ThermalKind.Reactor || spec.Rotary || !(terminal is IMyFunctionalBlock) || ((IMyFunctionalBlock)terminal).Enabled);
                var node = ThermalEndpoint.At(block.FatBlock == null ? -i-1 : block.FatBlock.EntityId,
                    block.CubeGrid.EntityId, spec, orientation, at, healthy);
                if (spec.Rotary && block.FatBlock != null)
                {
                    var native = rotary.Find(joint => joint.Id == block.FatBlock.EntityId);
                    node.Healthy = native != null && native.Healthy;
                    node.RotaryPeerId = native == null ? 0 : native.RotaryPeerId;
                }
                nodes.Add(node);
                if (!preview && block == aimed)
                { selected = node; rotation = orientation; centre = at; }
            }
            if (preview)
            {
                selected = ThermalEndpoint.At(0, grid.EntityId, model, rotation, centre, false);
                nodes.Add(selected);
            }
            if (selected == null) return;
            check = ThermalConstruction.Inspect(nodes, selected.Id);
            if (model.Kind == ThermalKind.Reactor)
            {
                var reactor = aimed.FatBlock == null ? null : VentSession.Find(aimed.FatBlock.EntityId);
                ShowReactorAssembly(aimed, reactor);
                return;
            }
            suggested = ThermalConstruction.Suggest(selected, rotation, centre, nodes);
            string next = check.Next;
            if (rotation != suggested) next = preview ? "Rotate preview toward GREEN; BLUE shows the H side"
                : "Rebuild the selected block in the indicated orientation; keep H aligned";
            if (grid.Physics == null) next = "Projection reference only: weld the physical grid before verification";
            Show(model, next, ServerStatus());
        }

        private string RadiatorGuide(ThermalModel model, IMySlimBlock aimed)
        {
            if (!preview)
            {
                aimed.Orientation.GetMatrix(out rotation);
                centre = aimed.FatBlock == null ? (Vector3)(aimed.Min + aimed.Max) * (grid.GridSize * .5f)
                    : ((MyEntity)aimed.FatBlock).PositionComp.LocalMatrixRef.Translation;
            }
            MatrixD panel = (MatrixD)rotation * grid.WorldMatrix;
            panel.Translation = Vector3D.Transform(centre, grid.WorldMatrix);
            blocks.Clear();
            grid.GetBlocks(blocks, b => ThermalModels.All.ContainsKey(b.BlockDefinition.Id.SubtypeName)
                && ThermalModels.All[b.BlockDefinition.Id.SubtypeName].Kind == ThermalKind.Radiator);
            double nearest = 25;
            IMySlimBlock source = null;
            int slot = 0;
            foreach (var block in blocks)
            {
                if (block.FatBlock == null) continue;
                var terminal = block.FatBlock as IMyTerminalBlock;
                if (terminal != null && !terminal.HasPlayerAccess(MyAPIGateway.Session.Player.IdentityId)) continue;
                for (int i = 0; i <= ThermalRadiators.MaxPanels; i++)
                {
                    double distance = Vector3D.DistanceSquared(panel.Translation,
                        ThermalRadiators.ExtensionCentre(block.FatBlock.WorldMatrix, i));
                    if (distance >= nearest) continue;
                    nearest = distance; source = block; slot = i;
                }
            }
            if (source == null) return "Aim at the TOP shaft coupling of a radiator base or preceding panel. Stack on the same grid; any yaw works.";
            radiatorFrame = source.FatBlock.WorldMatrix;
            radiatorDock = ThermalRadiators.ExtensionCentre(radiatorFrame, slot) - radiatorFrame.Up * 2.5;
            radiatorGuide = true;
            selected = ThermalEndpoint.At(0, grid.EntityId, model, rotation, centre, false);
            radiatorAligned = ThermalRadiators.FitsExtension(radiatorFrame, panel, slot);
            if (slot >= ThermalRadiators.MaxPanels) return "Maximum three panels per base. Start another radiator stack.";
            if (Vector3D.Dot(radiatorFrame.Up, panel.Up) <= .99999)
                return "Tilt until RED axis matches GREEN. BLUE shows panel Up; yaw aligns automatically.";
            if (!radiatorAligned)
                return "Centre the shaft over the highlighted TOP coupling. Keep BLUE pointing Up with the base; any yaw works.";
            for (int i = 0; i < slot; i++)
            {
                var lower = grid.GetCubeBlock(grid.WorldToGridInteger(ThermalRadiators.ExtensionCentre(radiatorFrame, i)));
                ThermalModel lowerModel;
                if (lower == null || lower.FatBlock == null
                    || !ThermalModels.All.TryGetValue(lower.BlockDefinition.Id.SubtypeName, out lowerModel)
                    || lowerModel.Kind != ThermalKind.RadiatorPanel
                    || !ThermalRadiators.FitsExtension(radiatorFrame, lower.FatBlock.WorldMatrix, i))
                {
                    radiatorAligned = false;
                    return "Place every preceding panel below this one. Panels must touch consecutively; any yaw works.";
                }
            }
            return preview ? "Stack alignment correct. Any yaw works; weld and enable the base and panels to align their moving parts."
                : ThermalSession.RadiatorConnection(aimed.FatBlock == null ? 0 : aimed.FatBlock.EntityId);
        }

        private IMySlimBlock Aim()
        {
            var camera = MyAPIGateway.Session.Camera.WorldMatrix;
            Vector3D start = camera.Translation + camera.Forward * .3, end = camera.Translation + camera.Forward * 20;
            VRage.Game.ModAPI.IHitInfo hit;
            if (!MyAPIGateway.Physics.CastRay(start, end, out hit) || hit == null || hit.HitEntity == null) return null;
            var target = hit.HitEntity.GetTopMostParent() as IMyCubeGrid;
            if (target == null) return null;
            Vector3I? at = target.RayCastBlocks(start, end);
            return at.HasValue ? target.GetCubeBlock(at.Value) : null;
        }

        private string ServerStatus()
        {
            if (check.Source == null || check.Source.Id <= 0) return "Place and connect the reactor to receive operating diagnostics";
            var sourceBlock = blocks.Find(b => b.FatBlock != null && b.FatBlock.EntityId == check.Source.Id);
            var fat = sourceBlock == null ? null : sourceBlock.FatBlock as IMyTerminalBlock;
            if (fat == null || !fat.HasPlayerAccess(MyAPIGateway.Session.Player.IdentityId)) return "Reactor access required";
            var source = VentSession.Find(fat.EntityId);
            if (source == null || source.Motion.Thermal == null || (!MyAPIGateway.Multiplayer.IsServer && source.Motion.Sequence == 0))
                return "Waiting for reactor operating state";
            var state = source.Motion.Thermal;
            if (state.Faulted) return "Runtime isolated: " + state.Diagnostic;
            if (state.Settled && state.Mode == ThermalMode.Brayton)
                for (int i = 0; i < state.Loops.Length; i++)
                    if (!state.Loops[i].Connected && check.Joints.Exists(j => j.Node == check.Source
                        && j.Port == check.Source.Ports[i] && j.Peer != null))
                        return "Circuit " + (i + 1) + " / valve closed: " + state.Loops[i].Diagnostic;
            return state.Mode + (state.Settled ? ": " : " / mode transition: ") + state.Diagnostic;
        }

        private void Show(ThermalModel model, string next, string server)
        {
            active = true;
            string label = preview ? "PLACEMENT" : "CONSTRUCTION CHECK";
            text.Clear().Append("<color=100,210,255>BRAYTON / ").Append(label)
                .Append("\n<color=235,240,245>").Append(model.Kind).Append(" / ")
                .Append(model.Cells.X).Append('x').Append(model.Cells.Y).Append('x').Append(model.Cells.Z).Append(" large grid\n")
                .Append(ThermalConstruction.Role(model)).Append("\n\n<color=255,210,110>").Append(next);
            if (check != null)
            {
                int matches = 0, total = 0, sealedUnions = 0;
                ThermalJointStatus issue = ThermalJointStatus.Matched;
                foreach (var joint in check.Joints)
                    if (joint.Node.Id == selected.Id)
                    {
                        total++;
                        if (joint.Status == ThermalJointStatus.Closed) sealedUnions++;
                        else if (joint.Status == ThermalJointStatus.Matched) matches++;
                        else if (issue == ThermalJointStatus.Matched || (issue == ThermalJointStatus.Open && joint.Status != ThermalJointStatus.Open)) issue = joint.Status;
                    }
                text.Append("\n<color=235,240,245>Selected sockets: ").Append(matches).Append('/').Append(total).Append(" aligned");
                if (sealedUnions > 0) text.Append(" / ").Append(sealedUnions).Append(" unused unions sealed");
                if (issue != ThermalJointStatus.Matched) text.Append(" / ").Append(ThermalConstruction.JointHint(issue));
                text.Append(selected.Model.Kind == ThermalKind.Reactor ? "\nReactor circuits: " : "\nSelected circuit: ")
                    .Append(check.Open).Append(" open mouths / ").Append(check.Wrong)
                    .Append(check.Wrong == 1 ? " mismatched connection / " : " mismatched connections / ")
                    .Append(check.Pending).Append(" unfinished or unavailable blocks");
                text.Append("\n<color=150,180,200>H = orange; C = cyan. Keep manifold circuits separate. Cap unused pipe mouths; unused reactor outlets stay closed.");
            }
            if (server != null) text.Append("\nServer: ").Append(server);
            text.Append("\nConstruction checks do not authorize startup. Cooling, power and reactor safeguards still apply.");
            if (preview) text.Append("\nSelected preview only: inspect line/mirror copies after placement.");
            Present("Thermal " + label.ToLowerInvariant() + ": " + next);
        }

        private void Present(string summary)
        {
            text.Append("\n<color=150,180,200>Type ").Append(GuideCommand).Append(" in chat to toggle this guide (saved).");
            WrapText();
            fallbackText = summary + " | " + GuideCommand + " toggles guide (saved)";
            if (!fullHud) return;
            if (panel != null && api.Heartbeat)
            {
                panel.Scale = assemblyBlock == null ? .72 : .62;
                panel.Visible = true;
            }
            else
            {
                if (fallback == null) fallback = MyAPIGateway.Utilities.CreateNotification("", 1000, "White");
                fallback.Text = fallbackText; fallback.ResetAliveTime(); fallback.Show();
            }
        }

        public override void Draw()
        {
            if (!active || grid == null || !Visible()) return;
            try
            {
                if (assemblyBlock != null) DrawAssemblyMarkers();
                if (selected == null) return;
                MatrixD world = grid.WorldMatrix;
                if (radiatorGuide)
                    Ring(radiatorDock, radiatorFrame.Right, radiatorFrame.Backward, .38,
                        (radiatorAligned ? new Color(20, 255, 85) : new Color(255, 180, 0)).ToVector4());
                else foreach (var joint in check.Joints)
                {
                    if (joint.Status == ThermalJointStatus.Closed) continue;
                    if (joint.Node.Id != selected.Id && joint.Status == ThermalJointStatus.Matched) continue;
                    IMyCubeGrid jointGrid;
                    if (!assemblyGrids.TryGetValue(joint.Node.GridId, out jointGrid) || jointGrid.Closed) continue;
                    MatrixD jointWorld = jointGrid.WorldMatrix;
                    var port = joint.Port;
                    Vector3D normal = Vector3D.TransformNormal(port.Normal, jointWorld);
                    Vector3D hot = Vector3D.TransformNormal(port.HotAxis, jointWorld);
                    Vector3D across = Vector3D.Cross(hot, normal);
                    Vector3D at = Vector3D.Transform(port.Position, jointWorld) + normal * .04;
                    if (Vector3D.DistanceSquared(at, MyAPIGateway.Session.Camera.WorldMatrix.Translation) > 25 * 25) continue;
                    bool aligned = joint.Status == ThermalJointStatus.Matched;
                    Vector4 color = aligned && joint.Node.Healthy && joint.Peer != null && joint.Peer.Healthy
                        ? new Color(20, 255, 85).ToVector4()
                        : aligned || joint.Status == ThermalJointStatus.Open ? new Color(255, 180, 0).ToVector4() : new Color(255, 25, 35).ToVector4();
                    Ring(at, hot, across, .85, color);
                    Ring(at + hot * .46, hot, across, .28, new Color(255, 85, 0).ToVector4());
                    Ring(at - hot * .46, hot, across, .28, new Color(0, 200, 255).ToVector4());
                }
                if (!fullHud || assemblyBlock != null) return;
                var camera = MyAPIGateway.Session.Camera.WorldMatrix;
                Vector3D point = preview ? previewWorld : Vector3D.Transform(centre, world);
                Vector3D ray = point - camera.Translation;
                if (Vector3D.Dot(ray, camera.Forward) <= 0 || ray.LengthSquared() < .001) return;
                double distance = ThermalMath.Clamp(ray.Length() * .35, .5, 6);
                Vector3D cluster = camera.Translation + Vector3D.Normalize(ray) * distance;
                double size = distance * .03;
                Vector3D blue = Vector3D.TransformNormal(rotation.Up, world);
                if (radiatorGuide)
                {
                    if (Vector3D.Dot(blue, radiatorFrame.Up) <= .99999)
                    {
                        Arrow(redArrow, blue, cluster, camera, size);
                        Arrow(greenArrow, radiatorFrame.Up, cluster, camera, size);
                        Turn(blue, radiatorFrame.Up, cluster, camera, size);
                    }
                }
                else if (rotation != suggested)
                {
                    Vector3 from = rotation.Forward, to = suggested.Forward;
                    if (Vector3.Dot(from, to) > .9999) { from = rotation.Up; to = suggested.Up; }
                    Vector3D current = Vector3D.TransformNormal(from, world), correct = Vector3D.TransformNormal(to, world);
                    Arrow(redArrow, current, cluster, camera, size);
                    Arrow(greenArrow, correct, cluster, camera, size);
                    Turn(current, correct, cluster, camera, size);
                }
                Arrow(blueArrow, radiatorGuide ? blue : Vector3D.TransformNormal(selected.Ports[0].HotAxis, world), cluster, camera, size);
            }
            catch (Exception error) { Log(error); }
        }

        private void WrapText()
        {
            string original = text.ToString();
            text.Clear();
            int column = 0; bool tag = false;
            foreach (char c in original)
            {
                if (c == '<') tag = true;
                if (c == '\n' || (!tag && c == ' ' && column >= 72))
                { text.Append('\n'); column = 0; continue; }
                text.Append(c);
                if (!tag) column++;
                if (c == '>') tag = false;
            }
        }

        private void Ring(Vector3D point, Vector3D up, Vector3D across, double radius, Vector4 color)
        {
            for (int i = 0; i < 16; i++)
            {
                double a = i * Math.PI / 8, b = (i + 1) * Math.PI / 8;
                Vector3D start = point + (up * Math.Cos(a) + across * Math.Sin(a)) * radius;
                Vector3D end = point + (up * Math.Cos(b) + across * Math.Sin(b)) * radius;
                Vector3D delta = end - start;
                MyTransparentGeometry.AddLineBillboard(lineMaterial, color, start, (Vector3)Vector3D.Normalize(delta),
                    (float)delta.Length(), .030f, BlendTypeEnum.PostPP);
            }
        }

        private static Vector3D Left(Vector3D up, MatrixD camera)
        {
            var left = Vector3D.Cross(camera.Forward, up);
            if (left.LengthSquared() < .000001) left = Vector3D.Cross(camera.Up, up);
            return Vector3D.Normalize(left);
        }

        private void Arrow(MyStringId material, Vector3D up, Vector3D point, MatrixD camera, double size)
        {
            MyTransparentGeometry.AddBillboardOriented(material, Vector4.One, point + up * (size * 2.2),
                (Vector3)Left(up, camera), (Vector3)up, (float)size, BlendTypeEnum.PostPP, -1);
        }

        private void Turn(Vector3D current, Vector3D correct, Vector3D point, MatrixD camera, double size)
        {
            Vector3D bisector, axis;
            if ((current + correct).LengthSquared() < .000001)
            { bisector = Left(current, camera); axis = Vector3D.Cross(current, bisector); }
            else { bisector = Vector3D.Normalize(current + correct); axis = Vector3D.Cross(current, correct); }
            double sign = Vector3D.Dot(axis, camera.Forward) < 0 ? 1 : -1;
            Vector3D left = Left(bisector, camera);
            const double cos45 = .70710678118;
            Vector3D up = (bisector - left * sign) * cos45;
            left = (left + bisector * sign) * cos45;
            MyTransparentGeometry.AddBillboardOriented(sign > 0 ? rightArrow : leftArrow, Vector4.One,
                point + bisector * (size * 3), (Vector3)left, (Vector3)up, (float)(size * .85), BlendTypeEnum.PostPP, -1);
        }

        private void Hide()
        {
            active = false; selected = null; check = null; radiatorGuide = radiatorAligned = false;
            assemblyBlock = null; assemblyReactor = null; assemblyDummies.Clear();
            if (panel != null) panel.Visible = false;
            if (fallback != null) fallback.Hide();
        }

        private void Log(Exception error)
        {
            if (loggedError) return;
            loggedError = true;
            MyLog.Default.WriteLine("ArcanePower: construction guide: " + error);
        }

        protected override void UnloadData()
        {
            if (chatSubscribed) MyAPIGateway.Utilities.MessageEntered -= GuideChat;
            chatSubscribed = false;
            Hide();
            if (api != null) api.Unload();
            api = null; panel = null; fallback = null;
        }
    }
}
