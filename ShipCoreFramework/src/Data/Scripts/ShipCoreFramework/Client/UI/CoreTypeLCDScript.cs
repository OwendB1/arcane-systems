using System;
using System.Collections.Generic;
using System.Globalization;
using Sandbox.Definitions;
using Sandbox.Game.Components;
using Sandbox.Game.GameSystems.TextSurfaceScripts;
using Sandbox.ModAPI;
using VRage.Game.ModAPI;
using VRage.Game.ModAPI.Ingame.Utilities;
using VRage.Game.GUI.TextPanel;
using VRageMath;
using IngameCubeBlock = VRage.Game.ModAPI.Ingame.IMyCubeBlock;
using IngameIMyEntity = VRage.Game.ModAPI.Ingame.IMyEntity;
using IngameTextSurface = Sandbox.ModAPI.Ingame.IMyTextSurface;
using IngameTextSurfaceProvider = Sandbox.ModAPI.Ingame.IMyTextSurfaceProvider;

namespace ShipCoreFramework
{
    [MyTextSurfaceScript("CoreTypeLCDScript", "Core status")]
    internal class CoreTypeLCDScript : MyTSSCommon
    {
        private const string CustomDataSection = "ShipCoreLCD";
        private const string FontSizeKey = "FontSize";
        private const string CombinePanelsKey = "CombinePanels";
        private const string ShowCursorKey = "ShowCursor";
        private const string PageKey = "Page";
        private const float DefaultFontScale = 1f;
        private const float MinFontScale = 0.45f;
        private const float MaxFontScale = 2.5f;
        private const float ManualScrollStepPixels = 72f;
        private const int CursorTimeoutTicks = 18;
        private const int ScrollInputTimeoutTicks = 60;
        private const int RedrawIntervalTicks = 10;
        private const double SamePlaneToleranceMeters = 0.08d;
        private const double TouchToleranceMeters = 0.08d;
        private const int MaxCombinedPanelMembers = 16;
        private const int MaxCombinedPanelCandidates = 64;
        private const float MaxCombinedVirtualPixels = 4096f;
        private const double MinScreenPixelsPerMeter = 16d;
        private const double MaxScreenPixelsPerMeter = 8192d;
        private const double MaxScreenAreaMeters = 8d;
        private const float BaselineLcdTextureResolution = 512f;
        private const float MinPhysicalRenderScale = 0.5f;
        private const float MaxPhysicalRenderScale = 1.5f;

        private static readonly object InstancesLock = new object();
        private static readonly List<CoreTypeLCDScript> Instances = new List<CoreTypeLCDScript>();
        private static readonly Dictionary<string, CursorState> CursorStates = new Dictionary<string, CursorState>(StringComparer.Ordinal);
        private static readonly Dictionary<string, ScrollState> ScrollStates = new Dictionary<string, ScrollState>(StringComparer.Ordinal);
        private static readonly Dictionary<string, int> PendingWheelDeltas = new Dictionary<string, int>(StringComparer.Ordinal);
        private static string _activeScrollGroupKey;
        private static int _activeScrollGroupTick = -1;
        private static int _lastInputSampleTick = -1;
        private static int _lastWheelInputTick = -1;
        private static int _nextInstanceId;

        private readonly int _instanceId;
        private readonly IMyTerminalBlock _terminalBlock;
        private readonly IMyCubeBlock _cubeBlock;
        private bool _disposed;
        private bool _surfaceIndexResolved;
        private int _surfaceIndex;
        private int _lastDrawTick = -RedrawIntervalTicks;
        private float _fontScale = DefaultFontScale;
        private bool _combinePanels = true;
        private bool _showCursor = true;
        private string _page = "Auto";

        public CoreTypeLCDScript(IMyTextSurface surface, IngameCubeBlock block, Vector2 size) : base(surface, block, size)
        {
            _terminalBlock = (IMyTerminalBlock)block;
            _cubeBlock = _terminalBlock;
            _instanceId = ++_nextInstanceId;
            _terminalBlock.OnMarkForClose += BlockMarkedForClose;
            ReloadCustomDataSettings();

            lock (InstancesLock)
            {
                Instances.Add(this);
            }
        }

        public override ScriptUpdate NeedsUpdate => ScriptUpdate.Update10;

        private GroupComponent GroupComponent => _terminalBlock?.GetGroupComponent();

        public override void Dispose()
        {
            if (_disposed) return;
            _disposed = true;

            lock (InstancesLock)
            {
                Instances.Remove(this);
            }

            if (_terminalBlock != null)
                _terminalBlock.OnMarkForClose -= BlockMarkedForClose;

            base.Dispose();
        }

        private void BlockMarkedForClose(IngameIMyEntity ent)
        {
            Dispose();
        }

        public override void Run()
        {
            try
            {
                base.Run();
                if (!Session.IsClient) return;

                SampleScrollInput();
                if (!ShouldDrawNow()) return;

                ReloadCustomDataSettings();

                if (Session.Config.SelectedNoCore == null)
                {
                    DrawMessage("SCF config missing", "No selected No Core config. Reload world after fixing config.");
                    return;
                }

                DrawDashboard();
                _lastDrawTick = Session.CurrentTick;
            }
            catch (Exception e)
            {
                DrawError(e);
            }
        }

        private void DrawDashboard()
        {
            var group = GroupComponent;
            if (group?.ShipCore == null)
            {
                DrawMessage("No ship core data", "Grid group not ready yet.");
                return;
            }

            var layout = BuildPanelGroupLayout();
            var hasCursorHit = UpdateCursorState(layout);

            var snapshot = BuildSnapshot(group, layout);
            var sprites = new List<MySprite>(128);
            Vector2 contentBottomRight;
            RenderDashboardSprites(sprites, snapshot, layout.VirtualSize, out contentBottomRight);

            var scrollOffset = UpdateManualScroll(layout, contentBottomRight.Y, hasCursorHit);
            var scroll = new Vector2(0f, scrollOffset);
            var frame = Surface.DrawFrame();
            frame.Add(new MySprite(SpriteType.TEXTURE, "SquareSimple", Surface.TextureSize * 0.5f,
                Surface.TextureSize, Color.Black));
            EmitSprites(frame, layout, sprites, scroll);
            RenderScrollIndicator(frame, layout, contentBottomRight.Y, scrollOffset);

            if (_showCursor)
                RenderCursor(frame, layout);

            frame.Dispose();
        }

        private CoreLcdSnapshot BuildSnapshot(GroupComponent group, PanelGroupLayout layout)
        {
            var snapshot = new CoreLcdSnapshot();
            var core = group.ShipCore;
            snapshot.CoreName = string.IsNullOrWhiteSpace(core.UniqueName) ? core.SubtypeId : core.UniqueName;
            snapshot.PanelCount = layout.MemberCount;

            var punishModifiers = group.PunishModifiers;
            var punishSpeed = group.PunishSpeed;
            var deactivated = group.Deactivated;
            var punishLimitedBlocks = group.PunishLimitedBlocks;

            float speed;
            long speedSourceGridId;
            lock (group.SpeedStateLock)
            {
                speed = group.EffectiveSpeedLimitMetersPerSecond;
                speedSourceGridId = group.SpeedSourceGroupGridId;
            }

            var speedLabel = IsSpeedSourceInGroup(group, speedSourceGridId) ? "Max Speed" : "Max Speed*";
            snapshot.Metrics.Add(new MetricRow(speedLabel, FormatDecimal(speed, "0.#") + " m/s", -1d, 0d, false));

            if (core.MaxBackupCores > 0)
            {
                var backupCores = Math.Max(0, group.CoreCount - 1);
                var fail = backupCores > core.MaxBackupCores;
                snapshot.Metrics.Add(new MetricRow("Backup Cores", backupCores.ToString(CultureInfo.InvariantCulture),
                    core.MaxBackupCores, core.MaxBackupCores > 0 ? backupCores / (double)core.MaxBackupCores : 0d, fail));
            }

            if (core.MaxBlocks > 1)
            {
                var maxBlocks = group.GetEffectiveMaxBlocks();
                var fail = group.GroupBlocksCount > maxBlocks;
                snapshot.Metrics.Add(new MetricRow("Blocks", FormatInt(group.GroupBlocksCount), maxBlocks,
                    maxBlocks > 0 ? group.GroupBlocksCount / (double)maxBlocks : 0d, fail));
            }

            if (core.MinBlocks > 0)
            {
                var fail = group.GroupBlocksCount < core.MinBlocks;
                var ratio = core.MinBlocks > 0 ? group.GroupBlocksCount / (double)core.MinBlocks : 0d;
                snapshot.Metrics.Add(new MetricRow("Min Blocks", FormatInt(group.GroupBlocksCount), core.MinBlocks,
                    ratio, fail, true));
            }

            if (core.MaxMass > 1)
            {
                var maxMass = group.GetEffectiveMaxMass();
                var fail = group.GroupMass > maxMass;
                snapshot.Metrics.Add(new MetricRow("Mass", FormatMass(group.GroupMass), maxMass,
                    maxMass > 0f ? group.GroupMass / (double)maxMass : 0d, fail));
            }

            if (core.MaxPCU > 1)
            {
                var maxPcu = group.GetEffectiveMaxPCU();
                var fail = group.GroupPCU > maxPcu;
                snapshot.Metrics.Add(new MetricRow("PCU", FormatInt(group.GroupPCU), maxPcu,
                    maxPcu > 0 ? group.GroupPCU / (double)maxPcu : 0d, fail));
            }

            snapshot.Flags.Add(new FlagRow("Modifiers", punishModifiers));
            snapshot.Flags.Add(new FlagRow("Speed", punishSpeed));
            snapshot.Flags.Add(new FlagRow("Limited blocks", punishLimitedBlocks));
            snapshot.Flags.Add(new FlagRow("Deactivated", deactivated));
            AddPunishmentReasons(snapshot, "Speed", group.GetSpeedPunishmentGateDescriptions());
            AddPunishmentReasons(snapshot, "Modifiers", group.GetModifierPunishmentGateDescriptions());
            AddPunishmentReasons(snapshot, "Limited Blocks", group.GetLimitedBlockPunishmentGateDescriptions());

            if (core.BlockLimits != null)
            {
                for (var i = 0; i < core.BlockLimits.Length; i++)
                {
                    var limit = core.BlockLimits[i];
                    if (limit == null) continue;
                    if (!group.ShouldEvaluateBlockLimit(limit)) continue;

                    var totalWeight = 0d;
                    LimitBucket bucket;
                    if (group.Limits.TryGetValue(limit, out bucket))
                        totalWeight = bucket.TotalWeight;

                    double max = group.GetEffectiveMaxCount(limit);
                    var fail = totalWeight > max;
                    var ratio = max > 0d ? totalWeight / max : 0d;
                    snapshot.Limits.Add(new LimitRow(limit.Name, totalWeight, max, ratio, limit.PunishmentType.ToString(), fail));
                }
            }

            snapshot.Limits.Sort(delegate(LimitRow left, LimitRow right)
            {
                var failCompare = right.Failing.CompareTo(left.Failing);
                if (failCompare != 0) return failCompare;
                return right.Ratio.CompareTo(left.Ratio);
            });

            var modifiers = group.Modifiers.GetModifierValues();
            for (var i = 0; i < modifiers.Count; i++)
                snapshot.Modifiers.Add(new ModifierRow(modifiers[i].Name, modifiers[i].Value));

            var warnings = 0;
            for (var i = 0; i < snapshot.Metrics.Count; i++)
                if (snapshot.Metrics[i].Failing)
                    warnings++;
            for (var i = 0; i < snapshot.Limits.Count; i++)
                if (snapshot.Limits[i].Failing)
                    warnings++;
            if (punishModifiers) warnings++;
            if (punishSpeed) warnings++;
            if (punishLimitedBlocks) warnings++;
            if (deactivated) warnings++;
            if (deactivated)
            {
                snapshot.StateText = "OFF";
                snapshot.StateColor = Palette.Red;
            }
            else if (warnings > 0)
            {
                snapshot.StateText = "ATTN";
                snapshot.StateColor = Palette.Amber;
            }
            else
            {
                snapshot.StateText = "OK";
                snapshot.StateColor = Palette.Green;
            }

            return snapshot;
        }

        private void RenderDashboardSprites(List<MySprite> sprites, CoreLcdSnapshot snapshot, Vector2 canvas,
            out Vector2 contentBottomRight)
        {
            var scale = _fontScale;
            var margin = 18f * scale;
            var bodyScale = 0.58f * scale;
            var smallScale = 0.48f * scale;
            var titleScale = 0.82f * scale;

            AddRect(sprites, 0f, 0f, canvas.X, 58f * scale, Palette.Header);
            AddText(sprites, "SCF", new Vector2(margin, 13f * scale), Palette.Muted, 0.62f * scale);
            AddText(sprites, TrimToWidth(snapshot.CoreName, Math.Max(80f, canvas.X - 260f * scale), titleScale),
                new Vector2(76f * scale, 10f * scale), Color.White, titleScale);
            AddPill(sprites, snapshot.StateText, snapshot.StateColor, new Vector2(canvas.X - 118f * scale, 11f * scale),
                new Vector2(94f * scale, 34f * scale), 0.56f * scale);
            if (snapshot.PanelCount > 1)
                AddText(sprites, snapshot.PanelCount.ToString(CultureInfo.InvariantCulture) + " panels",
                    new Vector2(canvas.X - 216f * scale, 19f * scale), Palette.Muted, smallScale);

            var y = 74f * scale;
            y = RenderMetricCards(sprites, snapshot, canvas, margin, y, bodyScale, smallScale);
            y += 12f * scale;
            y = RenderFlags(sprites, snapshot, canvas, margin, y, smallScale);
            y += 14f * scale;
            y = RenderPunishmentReasons(sprites, snapshot, canvas, margin, y, bodyScale, smallScale);

            var showAll = IsPage("All") || IsPage("Auto") && canvas.X >= 900f;
            var showOverview = IsPage("Overview") || IsPage("Auto");
            var showLimits = showAll || showOverview || IsPage("Limits");
            var showModifiers = showAll || IsPage("Modifiers");

            if (showLimits)
            {
                var limitRows = showAll || IsPage("Limits") ? snapshot.Limits.Count : Math.Min(snapshot.Limits.Count, 8);
                y = RenderLimits(sprites, snapshot, canvas, margin, y, bodyScale, smallScale, limitRows);
                y += 14f * scale;
            }

            if (showModifiers)
                y = RenderModifiers(sprites, snapshot, canvas, margin, y, bodyScale, smallScale);

            if (!showLimits && !showModifiers)
            {
                AddText(sprites, "Unknown page: " + _page, new Vector2(margin, y), Palette.Red, bodyScale);
                y += TextUtils.GetLineHeight(bodyScale);
            }

            contentBottomRight = new Vector2(canvas.X, y + margin);
        }

        private float RenderMetricCards(List<MySprite> sprites, CoreLcdSnapshot snapshot, Vector2 canvas, float margin,
            float y, float bodyScale, float smallScale)
        {
            var columns = canvas.X >= 980f ? 4 : canvas.X >= 560f ? 3 : 2;
            var gap = 10f * _fontScale;
            var cardW = (canvas.X - margin * 2f - gap * (columns - 1)) / columns;
            var cardH = 78f * _fontScale;

            for (var i = 0; i < snapshot.Metrics.Count; i++)
            {
                var col = i % columns;
                var row = i / columns;
                var x = margin + col * (cardW + gap);
                var cardY = y + row * (cardH + gap);
                var metric = snapshot.Metrics[i];
                var border = metric.Failing ? Palette.Red : Palette.Border;

                AddRect(sprites, x, cardY, cardW, cardH, Palette.Panel);
                AddRect(sprites, x, cardY, 3f * _fontScale, cardH, border);
                AddText(sprites, metric.Name, new Vector2(x + 11f * _fontScale, cardY + 9f * _fontScale), Palette.Muted, smallScale);
                AddText(sprites, metric.Value, new Vector2(x + 11f * _fontScale, cardY + 31f * _fontScale),
                    metric.Failing ? Palette.Red : Color.White, bodyScale);
                if (metric.Max > 0d)
                {
                    AddProgress(sprites, x + 11f * _fontScale, cardY + 61f * _fontScale, cardW - 22f * _fontScale,
                        6f * _fontScale, metric.Ratio, metric.Failing, metric.MinimumTarget);
                }
            }

            var rows = (snapshot.Metrics.Count + columns - 1) / columns;
            return y + rows * cardH + Math.Max(0, rows - 1) * gap;
        }

        private float RenderFlags(List<MySprite> sprites, CoreLcdSnapshot snapshot, Vector2 canvas, float margin, float y,
            float smallScale)
        {
            var x = margin;
            var pillH = 24f * _fontScale;
            var gap = 8f * _fontScale;
            for (var i = 0; i < snapshot.Flags.Count; i++)
            {
                var flag = snapshot.Flags[i];
                var text = flag.Name + ": " + (flag.Active ? "YES" : "NO");
                var width = Math.Max(92f * _fontScale, TextUtils.GetTextWidth(text, smallScale) + 18f * _fontScale);
                if (x + width > canvas.X - margin)
                {
                    x = margin;
                    y += pillH + gap;
                }

                AddPill(sprites, text, flag.Active ? Palette.Red : Palette.Green, new Vector2(x, y),
                    new Vector2(width, pillH), smallScale);
                x += width + gap;
            }

            return y + pillH;
        }

        private static void AddPunishmentReasons(CoreLcdSnapshot snapshot, string category, List<string> reasons)
        {
            for (var i = 0; i < reasons.Count; i++)
                snapshot.PunishmentReasons.Add(category + ": " + reasons[i]);
        }

        private float RenderPunishmentReasons(List<MySprite> sprites, CoreLcdSnapshot snapshot, Vector2 canvas,
            float margin, float y, float bodyScale, float smallScale)
        {
            if (snapshot.PunishmentReasons.Count == 0) return y;

            AddSectionTitle(sprites, "Punishment Reasons", y, margin, bodyScale);
            y += 34f * _fontScale;

            var maxWidth = canvas.X - margin * 2f - 12f * _fontScale;
            for (var i = 0; i < snapshot.PunishmentReasons.Count; i++)
            {
                var text = WrapToWidth("- " + snapshot.PunishmentReasons[i], maxWidth, smallScale);
                AddText(sprites, text, new Vector2(margin + 6f * _fontScale, y), Palette.Amber, smallScale);
                y += TextUtils.GetTextHeight(text, smallScale) + 5f * _fontScale;
            }

            return y + 9f * _fontScale;
        }

        private float RenderLimits(List<MySprite> sprites, CoreLcdSnapshot snapshot, Vector2 canvas, float margin, float y,
            float bodyScale, float smallScale, int rowLimit)
        {
            AddSectionTitle(sprites, "Block Limits", y, margin, bodyScale);
            y += 34f * _fontScale;

            if (snapshot.Limits.Count == 0)
            {
                AddText(sprites, "No configured block limits.", new Vector2(margin, y), Palette.Muted, bodyScale);
                return y + TextUtils.GetLineHeight(bodyScale);
            }

            var nameW = Math.Max(120f * _fontScale, canvas.X * 0.34f);
            var countW = 145f * _fontScale;
            var punishW = Math.Max(110f * _fontScale, canvas.X - margin * 2f - nameW - countW - 130f * _fontScale);
            var barW = Math.Max(70f * _fontScale, canvas.X - margin * 2f - nameW - countW - punishW - 16f * _fontScale);
            var rowH = 28f * _fontScale;
            var rows = Math.Min(rowLimit, snapshot.Limits.Count);

            AddText(sprites, "Limit", new Vector2(margin, y), Palette.Muted, smallScale);
            AddText(sprites, "Used", new Vector2(margin + nameW, y), Palette.Muted, smallScale);
            AddText(sprites, "Punishment", new Vector2(margin + nameW + countW + barW + 16f * _fontScale, y), Palette.Muted, smallScale);
            y += rowH;

            for (var i = 0; i < rows; i++)
            {
                var row = snapshot.Limits[i];
                var rowColor = row.Failing ? Palette.Red : Color.White;
                AddRect(sprites, margin, y - 3f * _fontScale, canvas.X - margin * 2f, rowH, i % 2 == 0 ? Palette.RowA : Palette.RowB);
                AddText(sprites, TrimToWidth(row.Name, nameW - 8f * _fontScale, smallScale), new Vector2(margin + 6f * _fontScale, y),
                    rowColor, smallScale);
                AddText(sprites, FormatLimitNumber(row.Used) + "/" + FormatLimitNumber(row.Max), new Vector2(margin + nameW, y),
                    rowColor, smallScale);
                AddProgress(sprites, margin + nameW + countW, y + 8f * _fontScale, barW, 6f * _fontScale, row.Ratio, row.Failing);
                AddText(sprites, TrimToWidth(row.Punishment, punishW, smallScale),
                    new Vector2(margin + nameW + countW + barW + 16f * _fontScale, y), Palette.Muted, smallScale);
                y += rowH;
            }

            if (rows < snapshot.Limits.Count)
            {
                AddText(sprites, "+" + (snapshot.Limits.Count - rows).ToString(CultureInfo.InvariantCulture) + " more",
                    new Vector2(margin, y + 2f * _fontScale), Palette.Muted, smallScale);
                y += rowH;
            }

            return y;
        }

        private float RenderModifiers(List<MySprite> sprites, CoreLcdSnapshot snapshot, Vector2 canvas, float margin, float y,
            float bodyScale, float smallScale)
        {
            AddSectionTitle(sprites, "Framework Modifiers", y, margin, bodyScale);
            y += 34f * _fontScale;

            var columns = canvas.X >= 760f ? 3 : 2;
            var gap = 10f * _fontScale;
            var cellW = (canvas.X - margin * 2f - gap * (columns - 1)) / columns;
            var rowH = 34f * _fontScale;

            for (var i = 0; i < snapshot.Modifiers.Count; i++)
            {
                var col = i % columns;
                var row = i / columns;
                var x = margin + col * (cellW + gap);
                var cellY = y + row * rowH;
                var modifier = snapshot.Modifiers[i];
                var valueColor = Math.Abs(modifier.Value - 1f) > 0.001f ? Palette.Cyan : Color.White;

                AddRect(sprites, x, cellY, cellW, rowH - 5f * _fontScale, Palette.Panel);
                AddText(sprites, TrimToWidth(modifier.Name, cellW - 64f * _fontScale, smallScale),
                    new Vector2(x + 9f * _fontScale, cellY + 7f * _fontScale), Palette.Muted, smallScale);
                AddText(sprites, FormatDecimal(modifier.Value, "0.###") + "x",
                    new Vector2(x + cellW - 56f * _fontScale, cellY + 7f * _fontScale), valueColor, smallScale);
            }

            var rows = (snapshot.Modifiers.Count + columns - 1) / columns;
            return y + rows * rowH;
        }

        private void AddSectionTitle(List<MySprite> sprites, string text, float y, float margin, float scale)
        {
            AddText(sprites, text, new Vector2(margin, y), Color.White, scale);
            AddRect(sprites, margin, y + 27f * _fontScale, 170f * _fontScale, 2f * _fontScale, Palette.Cyan);
        }

        private PanelGroupLayout BuildPanelGroupLayout()
        {
            LcdSurfaceLayout current;
            var hasCurrentLayout = TryGetSurfaceLayout(out current);
            var singleRenderScale = GetPhysicalRenderScale(hasCurrentLayout ? current.PixelsPerMeter : 0d);
            var single = PanelGroupLayout.Single(Surface.SurfaceSize, GetMemberKey(), singleRenderScale);
            if (!_combinePanels || _cubeBlock?.CubeGrid == null || !hasCurrentLayout)
                return single;

            var scripts = new List<CoreTypeLCDScript>();
            lock (InstancesLock)
            {
                for (var i = 0; i < Instances.Count; i++)
                    scripts.Add(Instances[i]);
            }

            var candidates = new List<LcdSurfaceLayout>();
            for (var i = 0; i < scripts.Count; i++)
            {
                var script = scripts[i];
                if (script == null || !script.IsUsableForGroup(_page, _cubeBlock.CubeGrid.EntityId)) continue;

                LcdSurfaceLayout layout;
                if (!script.TryGetSurfaceLayout(out layout)) continue;
                if (!IsSamePanelPlane(current, layout)) continue;

                var delta = layout.Center - current.Center;
                var x = Vector3D.Dot(delta, current.Right);
                var y = -Vector3D.Dot(delta, current.Up);
                layout.Rect = new PanelRect(x - layout.WidthM * 0.5d, y - layout.HeightM * 0.5d,
                    x + layout.WidthM * 0.5d, y + layout.HeightM * 0.5d);
                candidates.Add(layout);
            }

            if (candidates.Count <= 1)
                return single;
            if (candidates.Count > MaxCombinedPanelCandidates)
                return single;

            var currentIndex = -1;
            for (var i = 0; i < candidates.Count; i++)
            {
                if (candidates[i].Owner == this)
                {
                    currentIndex = i;
                    break;
                }
            }

            if (currentIndex < 0)
                return single;

            var connected = new bool[candidates.Count];
            connected[currentIndex] = true;
            bool changed;
            do
            {
                changed = false;
                for (var i = 0; i < candidates.Count; i++)
                {
                    if (!connected[i]) continue;

                    for (var j = 0; j < candidates.Count; j++)
                    {
                        if (connected[j]) continue;
                        if (!PanelRect.Touching(candidates[i].Rect, candidates[j].Rect, TouchToleranceMeters)) continue;
                        connected[j] = true;
                        changed = true;
                    }
                }
            }
            while (changed);

            var members = new List<LcdSurfaceLayout>();
            for (var i = 0; i < candidates.Count; i++)
                if (connected[i])
                    members.Add(candidates[i]);

            if (members.Count <= 1)
                return single;
            if (members.Count > MaxCombinedPanelMembers)
                return single;

            var minX = double.MaxValue;
            var minY = double.MaxValue;
            var maxX = double.MinValue;
            var maxY = double.MinValue;
            var ppmTotal = 0d;
            for (var i = 0; i < members.Count; i++)
            {
                var rect = members[i].Rect;
                if (rect.MinX < minX) minX = rect.MinX;
                if (rect.MinY < minY) minY = rect.MinY;
                if (rect.MaxX > maxX) maxX = rect.MaxX;
                if (rect.MaxY > maxY) maxY = rect.MaxY;
                ppmTotal += members[i].PixelsPerMeter;
            }

            var ppm = ppmTotal / members.Count;
            if (ppm <= 1d) return single;

            current.Rect = candidates[currentIndex].Rect;
            var scaleX = (float)(current.PixelsPerMeterX / ppm);
            var scaleY = (float)(current.PixelsPerMeterY / ppm);
            var virtualSize = new Vector2((float)((maxX - minX) * ppm), (float)((maxY - minY) * ppm));
            var renderScale = GetPhysicalRenderScale(ppm);
            if (virtualSize.X <= 1f || virtualSize.Y <= 1f ||
                virtualSize.X / renderScale > MaxCombinedVirtualPixels ||
                virtualSize.Y / renderScale > MaxCombinedVirtualPixels)
                return single;

            var viewportMin = new Vector2((float)((current.Rect.MinX - minX) * ppm), (float)((current.Rect.MinY - minY) * ppm));
            var key = BuildGroupKey(members);
            return new PanelGroupLayout(virtualSize, viewportMin, scaleX, scaleY, key, members.Count, renderScale);
        }

        private float GetPhysicalRenderScale(double pixelsPerMeter)
        {
            float definitionScale;
            if (TryGetDefinitionRenderScale(out definitionScale))
                return definitionScale;

            if (pixelsPerMeter <= 0d || Surface == null || _cubeBlock?.CubeGrid == null)
                return 1f;
            if (Surface.TextureSize.X <= 1f || Surface.TextureSize.Y <= 1f ||
                _cubeBlock.CubeGrid.GridSize <= 0.01f)
                return 1f;

            double referencePixelsPerMeter = Math.Min(Surface.TextureSize.X, Surface.TextureSize.Y) /
                                             _cubeBlock.CubeGrid.GridSize;
            if (referencePixelsPerMeter <= 0d) return 1f;

            var renderScale = pixelsPerMeter / referencePixelsPerMeter;
            if (renderScale < MinPhysicalRenderScale) renderScale = MinPhysicalRenderScale;
            if (renderScale > MaxPhysicalRenderScale) renderScale = MaxPhysicalRenderScale;
            return (float)renderScale;
        }

        private bool TryGetDefinitionRenderScale(out float renderScale)
        {
            renderScale = 1f;
            if (!(_cubeBlock is IMyTextPanel) || Surface == null || _cubeBlock.SlimBlock == null)
                return false;

            var definition = _cubeBlock.SlimBlock.BlockDefinition as MyFunctionalBlockDefinition;
            var surfaceIndex = ResolveSurfaceIndex();
            if (definition?.ScreenAreas == null || surfaceIndex < 0 ||
                surfaceIndex >= definition.ScreenAreas.Count)
                return false;

            var area = definition.ScreenAreas[surfaceIndex];
            if (area == null || area.TextureResolution <= 0 || area.ScreenWidth <= 0 || area.ScreenHeight <= 0)
                return false;

            var scaleX = Surface.SurfaceSize.X / (area.TextureResolution * (float)area.ScreenWidth);
            var scaleY = Surface.SurfaceSize.Y / (area.TextureResolution * (float)area.ScreenHeight);
            renderScale = Math.Min(scaleX, scaleY);
            renderScale = Math.Max(MinPhysicalRenderScale, Math.Min(MaxPhysicalRenderScale, renderScale));
            renderScale *= area.TextureResolution / BaselineLcdTextureResolution;
            renderScale = Math.Max(MinPhysicalRenderScale, Math.Min(MaxPhysicalRenderScale, renderScale));
            return true;
        }

        private bool TryGetSurfaceLayout(out LcdSurfaceLayout layout)
        {
            layout = null;
            if (_cubeBlock == null || Surface == null) return false;

            var surfaceIndex = ResolveSurfaceIndex();
            MatrixD worldMatrix;
            double widthM;
            double heightM;
            if (!ScfScreenAreaGeometry.TryGetScreenWorldMatrix(_cubeBlock, surfaceIndex, out worldMatrix) ||
                !ScfScreenAreaGeometry.TryGetScreenAreaSize(_cubeBlock, surfaceIndex, out widthM, out heightM))
                return false;

            if (widthM <= 0.01d || heightM <= 0.01d) return false;
            if (widthM > MaxScreenAreaMeters || heightM > MaxScreenAreaMeters) return false;
            if (Surface.SurfaceSize.X <= 1f || Surface.SurfaceSize.Y <= 1f) return false;

            var pixelsPerMeterX = Surface.SurfaceSize.X / widthM;
            var pixelsPerMeterY = Surface.SurfaceSize.Y / heightM;
            if (pixelsPerMeterX < MinScreenPixelsPerMeter || pixelsPerMeterX > MaxScreenPixelsPerMeter ||
                pixelsPerMeterY < MinScreenPixelsPerMeter || pixelsPerMeterY > MaxScreenPixelsPerMeter)
                return false;

            var right = worldMatrix.Right;
            var up = worldMatrix.Up;
            var normal = worldMatrix.Forward;
            if (!Normalize(ref right) || !Normalize(ref up) || !Normalize(ref normal)) return false;

            layout = new LcdSurfaceLayout
            {
                Owner = this,
                Center = worldMatrix.Translation,
                Right = right,
                Up = up,
                Normal = normal,
                WidthM = widthM,
                HeightM = heightM,
                PixelsPerMeterX = pixelsPerMeterX,
                PixelsPerMeterY = pixelsPerMeterY,
                MemberKey = GetMemberKey()
            };
            layout.PixelsPerMeter = (layout.PixelsPerMeterX + layout.PixelsPerMeterY) * 0.5d;
            layout.Rect = new PanelRect(-widthM * 0.5d, -heightM * 0.5d, widthM * 0.5d, heightM * 0.5d);
            return true;
        }

        private bool IsUsableForGroup(string page, long gridId)
        {
            if (_disposed || _cubeBlock?.CubeGrid == null || Surface == null) return false;
            if (!_combinePanels) return false;
            if (_cubeBlock.CubeGrid.EntityId != gridId) return false;
            return string.Equals(_page, page, StringComparison.OrdinalIgnoreCase);
        }

        private static bool IsSamePanelPlane(LcdSurfaceLayout current, LcdSurfaceLayout candidate)
        {
            if (current == null || candidate == null) return false;
            if (Vector3D.Dot(current.Normal, candidate.Normal) < 0.996d) return false;
            if (Vector3D.Dot(current.Right, candidate.Right) < 0.996d) return false;
            if (Vector3D.Dot(current.Up, candidate.Up) < 0.996d) return false;

            var planeDistance = Math.Abs(Vector3D.Dot(candidate.Center - current.Center, current.Normal));
            return planeDistance <= SamePlaneToleranceMeters;
        }

        private static bool Normalize(ref Vector3D vector)
        {
            if (vector.LengthSquared() <= 1e-12d) return false;
            vector.Normalize();
            return true;
        }

        private string BuildGroupKey(List<LcdSurfaceLayout> members)
        {
            var keys = new List<string>(members.Count);
            for (var i = 0; i < members.Count; i++)
                keys.Add(members[i].MemberKey);
            keys.Sort(StringComparer.Ordinal);
            return string.Join("|", keys.ToArray());
        }

        private string GetMemberKey()
        {
            var entityId = _cubeBlock?.EntityId ?? _instanceId;
            return entityId.ToString(CultureInfo.InvariantCulture) + "#" + ResolveSurfaceIndex().ToString(CultureInfo.InvariantCulture);
        }

        private int ResolveSurfaceIndex()
        {
            if (_surfaceIndexResolved) return _surfaceIndex;
            _surfaceIndexResolved = true;
            _surfaceIndex = 0;

            if (_cubeBlock is IMyTextPanel)
            {
                foreach (var component in _cubeBlock.Components)
                {
                    var lcdSurfaceComponent = component as IMyLcdSurfaceComponent;
                    if (lcdSurfaceComponent == null) continue;

                    _surfaceIndex = lcdSurfaceComponent.SelectedRotationIndex;
                    return _surfaceIndex;
                }
            }

            var provider = _terminalBlock as IngameTextSurfaceProvider;
            if (provider == null || Surface == null) return _surfaceIndex;

            var surfaceName = Surface.Name;
            for (var i = 0; i < provider.SurfaceCount; i++)
            {
                var surface = provider.GetSurface(i);
                if (surface == null) continue;
                if (ReferenceEquals(surface, Surface) ||
                    string.Equals(surface.Name, surfaceName, StringComparison.Ordinal))
                {
                    _surfaceIndex = i;
                    return _surfaceIndex;
                }
            }

            return _surfaceIndex;
        }

        private bool UpdateCursorState(PanelGroupLayout layout)
        {
            if (layout == null || _cubeBlock == null || MyAPIGateway.Session == null ||
                MyAPIGateway.Session.Camera == null)
                return false;

            var origin = MyAPIGateway.Session.Camera.WorldMatrix.Translation;
            var direction = MyAPIGateway.Session.Camera.WorldMatrix.Forward;
            if (Vector3D.DistanceSquared(origin, _cubeBlock.WorldMatrix.Translation) > 10000d)
                return false;

            Vector2 screenPoint;
            if (!ScfScreenAreaGeometry.TryGetScreenPointIntersection(_cubeBlock, ResolveSurfaceIndex(), Surface, origin,
                    direction, out screenPoint))
                return false;

            var screenTopLeft = (Surface.TextureSize - Surface.SurfaceSize) * 0.5f;
            var visible = screenPoint - screenTopLeft;
            if (visible.X < 0f || visible.Y < 0f || visible.X > Surface.SurfaceSize.X || visible.Y > Surface.SurfaceSize.Y)
                return false;

            var virtualPoint = new Vector2(
                layout.ViewportMin.X + visible.X / Math.Max(0.001f, layout.ScaleX),
                layout.ViewportMin.Y + visible.Y / Math.Max(0.001f, layout.ScaleY));

            CursorStates[layout.GroupKey] = new CursorState
            {
                Position = virtualPoint,
                Tick = Session.CurrentTick
            };
            _activeScrollGroupKey = layout.GroupKey;
            _activeScrollGroupTick = Session.CurrentTick;

            return true;
        }

        private void RenderCursor(MySpriteDrawFrame frame, PanelGroupLayout layout)
        {
            CursorState state;
            if (!CursorStates.TryGetValue(layout.GroupKey, out state)) return;
            if (Session.CurrentTick - state.Tick > CursorTimeoutTicks) return;

            var cursor = new List<MySprite>(6);
            var r = 8f * _fontScale;
            var thickness = 2f * _fontScale;
            AddRect(cursor, state.Position.X - r, state.Position.Y - thickness * 0.5f, r * 2f, thickness, Palette.Cursor);
            AddRect(cursor, state.Position.X - thickness * 0.5f, state.Position.Y - r, thickness, r * 2f, Palette.Cursor);
            AddRect(cursor, state.Position.X - 2f * _fontScale, state.Position.Y - 2f * _fontScale,
                4f * _fontScale, 4f * _fontScale, Color.White);
            EmitSprites(frame, layout, cursor, Vector2.Zero);
        }

        private void EmitSprites(MySpriteDrawFrame frame, PanelGroupLayout layout, List<MySprite> sprites, Vector2 scroll)
        {
            var screenTopLeft = (Surface.TextureSize - Surface.SurfaceSize) * 0.5f;
            var clipMin = layout.ViewportMin;
            var clipMax = layout.ViewportMin + new Vector2(
                Surface.SurfaceSize.X / layout.ScaleX,
                Surface.SurfaceSize.Y / layout.ScaleY);

            for (var i = 0; i < sprites.Count; i++)
            {
                var sprite = sprites[i];
                if (sprite.Type == SpriteType.TEXTURE && sprite.Position.HasValue && sprite.Size.HasValue)
                {
                    var center = sprite.Position.Value;
                    center.Y -= scroll.Y;
                    var size = sprite.Size.Value;
                    if (!ClipVirtualRect(ref center, ref size, clipMin, clipMax)) continue;

                    sprite.Position = new Vector2(
                        screenTopLeft.X + (center.X - layout.ViewportMin.X) * layout.ScaleX,
                        screenTopLeft.Y + (center.Y - layout.ViewportMin.Y) * layout.ScaleY);
                    sprite.Size = new Vector2(size.X * layout.ScaleX, size.Y * layout.ScaleY);
                    frame.Add(sprite);
                    continue;
                }

                if (sprite.Position.HasValue)
                {
                    var p = sprite.Position.Value;
                    p.Y -= scroll.Y;
                    if (sprite.Type == SpriteType.TEXT && !IsVirtualTextVisible(p, clipMin, clipMax))
                        continue;

                    p = new Vector2(
                        screenTopLeft.X + (p.X - layout.ViewportMin.X) * layout.ScaleX,
                        screenTopLeft.Y + (p.Y - layout.ViewportMin.Y) * layout.ScaleY);
                    sprite.Position = p;
                }

                if (sprite.Size.HasValue)
                {
                    var size = sprite.Size.Value;
                    sprite.Size = new Vector2(size.X * layout.ScaleX, size.Y * layout.ScaleY);
                }

                if (sprite.Type == SpriteType.TEXT)
                    sprite.RotationOrScale *= layout.TextScale;

                frame.Add(sprite);
            }
        }

        private static bool ClipVirtualRect(ref Vector2 center, ref Vector2 size, Vector2 clipMin, Vector2 clipMax)
        {
            if (size.X <= 0f || size.Y <= 0f) return false;

            var minX = center.X - size.X * 0.5f;
            var maxX = center.X + size.X * 0.5f;
            var minY = center.Y - size.Y * 0.5f;
            var maxY = center.Y + size.Y * 0.5f;

            minX = Math.Max(minX, clipMin.X);
            maxX = Math.Min(maxX, clipMax.X);
            minY = Math.Max(minY, clipMin.Y);
            maxY = Math.Min(maxY, clipMax.Y);

            if (maxX <= minX || maxY <= minY) return false;

            center = new Vector2((minX + maxX) * 0.5f, (minY + maxY) * 0.5f);
            size = new Vector2(maxX - minX, maxY - minY);
            return true;
        }

        private static bool IsVirtualTextVisible(Vector2 position, Vector2 clipMin, Vector2 clipMax)
        {
            return position.X >= clipMin.X - 420f &&
                   position.X <= clipMax.X + 80f &&
                   position.Y >= clipMin.Y - 80f &&
                   position.Y <= clipMax.Y + 80f;
        }

        private float UpdateManualScroll(PanelGroupLayout layout, float contentHeight, bool hasCursorHit)
        {
            if (layout == null || string.IsNullOrEmpty(layout.GroupKey)) return 0f;

            var state = GetScrollState(layout.GroupKey);
            var maxScroll = Math.Max(0f, contentHeight - layout.VirtualSize.Y);
            if (maxScroll <= 0f)
            {
                state.Offset = 0f;
                return 0f;
            }

            var wheelDelta = ConsumePendingWheelDelta(layout.GroupKey);
            var canScroll = hasCursorHit || IsGroupCursorActive(layout);
            if (canScroll && wheelDelta != 0 && state.LastInputTick != Session.CurrentTick)
            {
                var step = ManualScrollStepPixels * Math.Max(0.25f, _fontScale);
                var steps = Math.Max(1f, Math.Abs(wheelDelta) / 120f);
                state.Offset += wheelDelta > 0 ? -step * steps : step * steps;
                state.LastInputTick = Session.CurrentTick;
            }

            state.Offset = Math.Max(0f, Math.Min(maxScroll, state.Offset));
            return state.Offset;
        }

        private bool ShouldDrawNow()
        {
            if (Session.CurrentTick - _lastDrawTick >= RedrawIntervalTicks)
                return true;

            return _lastWheelInputTick == Session.CurrentTick;
        }

        internal static void SampleScrollInput()
        {
            if (_lastInputSampleTick == Session.CurrentTick) return;
            _lastInputSampleTick = Session.CurrentTick;

            if (MyAPIGateway.Input == null) return;
            if (string.IsNullOrEmpty(_activeScrollGroupKey)) return;
            if (Session.CurrentTick - _activeScrollGroupTick > ScrollInputTimeoutTicks) return;

            var wheelDelta = MyAPIGateway.Input.DeltaMouseScrollWheelValue();
            if (wheelDelta == 0) return;

            int pending;
            PendingWheelDeltas.TryGetValue(_activeScrollGroupKey, out pending);
            PendingWheelDeltas[_activeScrollGroupKey] = pending + wheelDelta;
            _lastWheelInputTick = Session.CurrentTick;
        }

        internal static void RunFrameScrollUpdate()
        {
            SampleScrollInput();
            if (_lastWheelInputTick != Session.CurrentTick) return;
            if (string.IsNullOrEmpty(_activeScrollGroupKey)) return;

            var scripts = new List<CoreTypeLCDScript>();
            lock (InstancesLock)
            {
                for (var i = 0; i < Instances.Count; i++)
                    scripts.Add(Instances[i]);
            }

            for (var i = 0; i < scripts.Count; i++)
            {
                var script = scripts[i];
                if (script == null || script._disposed) continue;
                if (!IsGroupKeyMember(_activeScrollGroupKey, script.GetMemberKey())) continue;
                script.DrawFromFrameScrollUpdate();
            }
        }

        private void DrawFromFrameScrollUpdate()
        {
            try
            {
                if (!Session.IsClient || Session.Config.SelectedNoCore == null) return;
                ReloadCustomDataSettings();
                DrawDashboard();
                _lastDrawTick = Session.CurrentTick;
            }
            catch (Exception e)
            {
                DrawError(e);
            }
        }

        private static bool IsGroupKeyMember(string groupKey, string memberKey)
        {
            if (string.IsNullOrEmpty(groupKey) || string.IsNullOrEmpty(memberKey)) return false;
            if (string.Equals(groupKey, memberKey, StringComparison.Ordinal)) return true;
            if (groupKey.StartsWith(memberKey + "|", StringComparison.Ordinal)) return true;
            if (groupKey.EndsWith("|" + memberKey, StringComparison.Ordinal)) return true;
            return groupKey.IndexOf("|" + memberKey + "|", StringComparison.Ordinal) >= 0;
        }

        private static int ConsumePendingWheelDelta(string groupKey)
        {
            if (string.IsNullOrEmpty(groupKey)) return 0;

            int wheelDelta;
            if (!PendingWheelDeltas.TryGetValue(groupKey, out wheelDelta)) return 0;

            PendingWheelDeltas.Remove(groupKey);
            return wheelDelta;
        }

        private static bool IsGroupCursorActive(PanelGroupLayout layout)
        {
            if (layout == null || string.IsNullOrEmpty(layout.GroupKey)) return false;

            CursorState state;
            if (!CursorStates.TryGetValue(layout.GroupKey, out state)) return false;
            return Session.CurrentTick - state.Tick <= CursorTimeoutTicks;
        }

        private static ScrollState GetScrollState(string key)
        {
            ScrollState state;
            if (!ScrollStates.TryGetValue(key, out state))
            {
                state = new ScrollState();
                ScrollStates[key] = state;
            }

            return state;
        }

        private void RenderScrollIndicator(MySpriteDrawFrame frame, PanelGroupLayout layout, float contentHeight,
            float scrollOffset)
        {
            if (layout == null || contentHeight <= layout.VirtualSize.Y + 1f) return;

            var maxScroll = Math.Max(1f, contentHeight - layout.VirtualSize.Y);
            var trackTop = 66f * _fontScale;
            var trackBottom = layout.VirtualSize.Y - 16f * _fontScale;
            var trackHeight = trackBottom - trackTop;
            if (trackHeight <= 20f) return;

            var trackWidth = 4f * _fontScale;
            var trackX = layout.VirtualSize.X - 10f * _fontScale;
            var thumbHeight = Math.Max(18f * _fontScale, trackHeight * layout.VirtualSize.Y / contentHeight);
            var thumbTravel = Math.Max(1f, trackHeight - thumbHeight);
            var thumbTop = trackTop + thumbTravel * (scrollOffset / maxScroll);

            var sprites = new List<MySprite>(2);
            AddRect(sprites, trackX, trackTop, trackWidth, trackHeight, Palette.BarBack.Alpha(0.65f));
            AddRect(sprites, trackX - 1f * _fontScale, thumbTop, trackWidth + 2f * _fontScale, thumbHeight,
                Palette.Muted.Alpha(0.9f));
            EmitSprites(frame, layout, sprites, Vector2.Zero);
        }

        private void AddText(List<MySprite> sprites, string text, Vector2 position, Color color, float scale)
        {
            var sprite = MySprite.CreateText(text ?? string.Empty, "Monospace", color, scale, TextAlignment.LEFT);
            sprite.Position = position;
            sprites.Add(sprite);
        }

        private void AddRect(List<MySprite> sprites, float x, float y, float w, float h, Color color)
        {
            if (w <= 0f || h <= 0f) return;
            sprites.Add(new MySprite(SpriteType.TEXTURE, "SquareSimple",
                new Vector2(x + w * 0.5f, y + h * 0.5f), new Vector2(w, h), color));
        }

        private void AddPill(List<MySprite> sprites, string text, Color color, Vector2 position, Vector2 size, float textScale)
        {
            AddRect(sprites, position.X, position.Y, size.X, size.Y, color.Alpha(0.22f));
            AddRect(sprites, position.X, position.Y, 3f * _fontScale, size.Y, color);
            AddText(sprites, text, new Vector2(position.X + 9f * _fontScale, position.Y + 6f * _fontScale), color, textScale);
        }

        private void AddProgress(List<MySprite> sprites, float x, float y, float w, float h, double ratio, bool failing,
            bool minimumTarget = false)
        {
            AddRect(sprites, x, y, w, h, Palette.BarBack);
            var clamped = Math.Max(0d, Math.Min(1d, ratio));
            var color = minimumTarget
                ? failing ? Palette.Amber : Palette.Green
                : failing ? Palette.Red : ratio >= 0.85d ? Palette.Amber : Palette.Green;
            AddRect(sprites, x, y, (float)(w * clamped), h, color);
            if (!minimumTarget && ratio > 1d)
                AddRect(sprites, x + w - 3f * _fontScale, y - 2f * _fontScale, 3f * _fontScale, h + 4f * _fontScale,
                    Palette.Red);
        }

        private string TrimToWidth(string text, float maxWidth, float scale)
        {
            if (string.IsNullOrEmpty(text)) return string.Empty;
            if (TextUtils.GetTextWidth(text, scale) <= maxWidth) return text;

            const string suffix = "...";
            var maxChars = Math.Max(1, (int)(maxWidth / (TextUtils.CharWidth * scale)) - suffix.Length);
            if (maxChars >= text.Length) return text;
            return text.Substring(0, maxChars) + suffix;
        }

        private static string WrapToWidth(string text, float maxWidth, float scale)
        {
            var maxChars = Math.Max(1, (int)(maxWidth / (TextUtils.CharWidth * scale)));
            if (string.IsNullOrEmpty(text) || text.Length <= maxChars) return text ?? string.Empty;

            var words = text.Split(new[] { ' ' }, StringSplitOptions.RemoveEmptyEntries);
            var lines = new List<string>();
            var line = string.Empty;
            for (var i = 0; i < words.Length; i++)
            {
                if (line.Length == 0)
                {
                    line = words[i];
                    continue;
                }

                if (line.Length + 1 + words[i].Length <= maxChars)
                {
                    line += " " + words[i];
                    continue;
                }

                lines.Add(line);
                line = "  " + words[i];
            }

            if (line.Length > 0) lines.Add(line);
            return string.Join("\n", lines);
        }

        private void DrawMessage(string title, string body)
        {
            var frame = Surface.DrawFrame();
            var screenSize = Surface.SurfaceSize;
            var screenTopLeft = (Surface.TextureSize - screenSize) * 0.5f;
            frame.Add(new MySprite(SpriteType.TEXTURE, "SquareSimple", Surface.TextureSize * 0.5f,
                Surface.TextureSize, Palette.Background));

            var titleSprite = MySprite.CreateText(title, "Monospace", Color.White, 0.85f * _fontScale, TextAlignment.LEFT);
            titleSprite.Position = screenTopLeft + new Vector2(18f * _fontScale, 18f * _fontScale);
            frame.Add(titleSprite);

            var bodySprite = MySprite.CreateText(body, "Monospace", Palette.Muted, 0.55f * _fontScale, TextAlignment.LEFT);
            bodySprite.Position = screenTopLeft + new Vector2(18f * _fontScale, 58f * _fontScale);
            frame.Add(bodySprite);
            frame.Dispose();
        }

        private void ReloadCustomDataSettings()
        {
            _fontScale = DefaultFontScale;
            _combinePanels = true;
            _showCursor = true;
            _page = "Auto";

            var customData = _terminalBlock?.CustomData;
            if (string.IsNullOrWhiteSpace(customData)) return;

            var ini = new MyIni();
            MyIniParseResult parseResult;
            if (!ini.TryParse(customData, out parseResult)) return;

            _fontScale = MathHelper.Clamp(ini.Get(CustomDataSection, FontSizeKey).ToSingle(DefaultFontScale),
                MinFontScale, MaxFontScale);
            _combinePanels = ini.Get(CustomDataSection, CombinePanelsKey).ToBoolean(true);
            _showCursor = ini.Get(CustomDataSection, ShowCursorKey).ToBoolean(true);

            var page = ini.Get(CustomDataSection, PageKey).ToString("Auto").Trim();
            if (IsKnownPage(page)) _page = page;
        }

        private bool IsPage(string page)
        {
            return string.Equals(_page, page, StringComparison.OrdinalIgnoreCase);
        }

        private static bool IsKnownPage(string page)
        {
            return string.Equals(page, "Auto", StringComparison.OrdinalIgnoreCase) ||
                   string.Equals(page, "Overview", StringComparison.OrdinalIgnoreCase) ||
                   string.Equals(page, "Limits", StringComparison.OrdinalIgnoreCase) ||
                   string.Equals(page, "Modifiers", StringComparison.OrdinalIgnoreCase) ||
                   string.Equals(page, "All", StringComparison.OrdinalIgnoreCase);
        }

        private static bool IsSpeedSourceInGroup(GroupComponent group, long gridId)
        {
            if (group == null || gridId == 0) return true;
            foreach (IMyCubeGrid grid in group.GridDictionary.Keys)
            {
                if (grid != null && grid.EntityId == gridId)
                    return true;
            }

            return false;
        }

        private static string FormatDecimal(float value, string format)
        {
            return value.ToString(format, CultureInfo.InvariantCulture);
        }

        private static string FormatInt(int value)
        {
            return value.ToString("N0", CultureInfo.InvariantCulture);
        }

        private static string FormatMass(float value)
        {
            if (Math.Abs(value) >= 1000000f)
                return (value / 1000000f).ToString("0.##", CultureInfo.InvariantCulture) + " Mt";
            if (Math.Abs(value) >= 1000f)
                return (value / 1000f).ToString("0.#", CultureInfo.InvariantCulture) + " t";
            return value.ToString("0", CultureInfo.InvariantCulture) + " kg";
        }

        private static string FormatLimitNumber(double value)
        {
            if (Math.Abs(value - Math.Round(value)) < 0.001d)
                return ((int)Math.Round(value)).ToString(CultureInfo.InvariantCulture);
            return value.ToString("0.##", CultureInfo.InvariantCulture);
        }

        private void DrawError(Exception e)
        {
            Utils.Log("Failed to draw LCD: " + e.Message + "\n" + e.StackTrace);

            try
            {
                var frame = Surface.DrawFrame();
                var screenSize = Surface.SurfaceSize;
                var screenCorner = (Surface.TextureSize - screenSize) * 0.5f;

                frame.Add(new MySprite(SpriteType.TEXTURE, "SquareSimple", Surface.TextureSize * 0.5f,
                    Surface.TextureSize, Color.Black));

                var text = MySprite.CreateText(
                    "ERROR: " + e.Message + "\n" + e.StackTrace + "\n\nPlease send screenshot to mod author.\n" +
                    MyAPIGateway.Utilities.GamePaths.ModScopeName,
                    "White", Color.Red, 0.55f, TextAlignment.LEFT);
                text.Position = screenCorner + new Vector2(16f, 16f);
                frame.Add(text);
                frame.Dispose();
            }
            catch (Exception e2)
            {
                Utils.Log("Also failed to draw error on screen: " + e2.Message + "\n" + e2.StackTrace);
            }
        }

        private static class Palette
        {
            internal static readonly Color Background = new Color(8, 10, 13, 255);
            internal static readonly Color Header = new Color(18, 24, 31, 255);
            internal static readonly Color Panel = new Color(24, 30, 38, 245);
            internal static readonly Color RowA = new Color(16, 20, 26, 225);
            internal static readonly Color RowB = new Color(22, 27, 34, 225);
            internal static readonly Color Border = new Color(65, 75, 85, 255);
            internal static readonly Color BarBack = new Color(48, 55, 64, 255);
            internal static readonly Color Muted = new Color(160, 170, 180, 255);
            internal static readonly Color Green = new Color(78, 210, 118, 255);
            internal static readonly Color Amber = new Color(255, 178, 66, 255);
            internal static readonly Color Red = new Color(238, 82, 82, 255);
            internal static readonly Color Cyan = new Color(70, 190, 220, 255);
            internal static readonly Color Cursor = new Color(255, 255, 255, 210);
        }

        private sealed class CoreLcdSnapshot
        {
            internal string CoreName;
            internal string StateText;
            internal Color StateColor;
            internal int PanelCount;
            internal readonly List<MetricRow> Metrics = new List<MetricRow>();
            internal readonly List<FlagRow> Flags = new List<FlagRow>();
            internal readonly List<string> PunishmentReasons = new List<string>();
            internal readonly List<LimitRow> Limits = new List<LimitRow>();
            internal readonly List<ModifierRow> Modifiers = new List<ModifierRow>();
        }

        private struct MetricRow
        {
            internal readonly string Name;
            internal readonly string Value;
            internal readonly double Max;
            internal readonly double Ratio;
            internal readonly bool Failing;
            internal readonly bool MinimumTarget;

            internal MetricRow(string name, string value, double max, double ratio, bool failing,
                bool minimumTarget = false)
            {
                Name = name;
                Value = value;
                Max = max;
                Ratio = ratio;
                Failing = failing;
                MinimumTarget = minimumTarget;
            }
        }

        private struct FlagRow
        {
            internal readonly string Name;
            internal readonly bool Active;

            internal FlagRow(string name, bool active)
            {
                Name = name;
                Active = active;
            }
        }

        private struct LimitRow
        {
            internal readonly string Name;
            internal readonly double Used;
            internal readonly double Max;
            internal readonly double Ratio;
            internal readonly string Punishment;
            internal readonly bool Failing;

            internal LimitRow(string name, double used, double max, double ratio, string punishment, bool failing)
            {
                Name = name;
                Used = used;
                Max = max;
                Ratio = ratio;
                Punishment = punishment;
                Failing = failing;
            }
        }

        private struct ModifierRow
        {
            internal readonly string Name;
            internal readonly float Value;

            internal ModifierRow(string name, float value)
            {
                Name = name;
                Value = value;
            }
        }

        private sealed class CursorState
        {
            internal Vector2 Position;
            internal int Tick;
        }

        private sealed class ScrollState
        {
            internal float Offset;
            internal int LastInputTick = -1;
        }

        private sealed class LcdSurfaceLayout
        {
            internal CoreTypeLCDScript Owner;
            internal Vector3D Center;
            internal Vector3D Right;
            internal Vector3D Up;
            internal Vector3D Normal;
            internal double WidthM;
            internal double HeightM;
            internal double PixelsPerMeterX;
            internal double PixelsPerMeterY;
            internal double PixelsPerMeter;
            internal PanelRect Rect;
            internal string MemberKey;
        }

        private sealed class PanelGroupLayout
        {
            internal readonly Vector2 VirtualSize;
            internal readonly Vector2 ViewportMin;
            internal readonly float ScaleX;
            internal readonly float ScaleY;
            internal readonly float TextScale;
            internal readonly string GroupKey;
            internal readonly int MemberCount;

            internal PanelGroupLayout(Vector2 virtualSize, Vector2 viewportMin, float scaleX, float scaleY, string groupKey,
                int memberCount, float renderScale)
            {
                renderScale = Math.Max(MinPhysicalRenderScale, Math.Min(MaxPhysicalRenderScale, renderScale));
                VirtualSize = virtualSize / renderScale;
                ViewportMin = viewportMin / renderScale;
                ScaleX = Math.Max(0.001f, scaleX * renderScale);
                ScaleY = Math.Max(0.001f, scaleY * renderScale);
                TextScale = Math.Min(ScaleX, ScaleY);
                GroupKey = groupKey;
                MemberCount = memberCount;
            }

            internal static PanelGroupLayout Single(Vector2 size, string key, float renderScale)
            {
                return new PanelGroupLayout(size, Vector2.Zero, 1f, 1f, key, 1, renderScale);
            }
        }

        private struct PanelRect
        {
            internal readonly double MinX;
            internal readonly double MinY;
            internal readonly double MaxX;
            internal readonly double MaxY;

            internal PanelRect(double minX, double minY, double maxX, double maxY)
            {
                MinX = minX;
                MinY = minY;
                MaxX = maxX;
                MaxY = maxY;
            }

            internal static bool Touching(PanelRect a, PanelRect b, double tolerance)
            {
                return a.MaxX + tolerance >= b.MinX &&
                       b.MaxX + tolerance >= a.MinX &&
                       a.MaxY + tolerance >= b.MinY &&
                       b.MaxY + tolerance >= a.MinY;
            }
        }
    }
}
