using System;
using System.Collections.Generic;
using VRageMath;

namespace ArcanePower
{
    public sealed class ThermalBuildCheck
    {
        public readonly List<ThermalJoint> Joints = new List<ThermalJoint>();
        public readonly List<ThermalEndpoint> Nodes = new List<ThermalEndpoint>();
        public ThermalEndpoint Source;
        public int Open, Wrong, Pending, Trains, Cooling;
        public bool Verified;
        public string Next;
    }

    // Construction is a read-only geometry/build check. It neither grants
    // startup permission nor substitutes client observations for server state.
    public static class ThermalConstruction
    {
        public static bool ShowReactorGuide(ThermalReactorState state, ThermalBuildCheck check)
        {
            return state != null && state.Mode == ThermalMode.Brayton && state.Settled
                && check != null && !check.Verified;
        }

        public static string Role(ThermalModel model)
        {
            switch (model.Kind)
            {
                case ThermalKind.Reactor: return "Stop/cool, select Brayton, deploy manifolds. Use reactor adapters; cap unused reactor sockets.";
                case ThermalKind.Train: return "One lower-cell duplex H/C socket on a 2x2x5 train. Branch turbines and coolers from the reactor's shared pipe network; use the mirrored turbine for the opposite side. Supply grid power for the built-in compressor startup.";
                case ThermalKind.RadiatorPanel: return "Stack directly above a radiator on the same grid and orientation. Up to two extension panels share its axis and cooling loop.";
                case ThermalKind.AirCooler: return "Connect the rear cooling socket. Mount casing flush in hull; keep 2.5 m clear beyond both front fan guards. Blocked exhaust stops cooling; needs atmosphere and circulation.";
                case ThermalKind.Radiator: return "Connect cooling underneath the pedestal. Panels automatically track edge-on to the sun; keep both faces open to space and the 3x3x3 sweep clear. Red glow shows heat dissipation.";
                default: return model.Subtype.EndsWith("ReactorAdapter") || model.Subtype.EndsWith("ReactorAdapterBare")
                    ? "Bridge the reactor's 170 mm socket offset to the standard 2.5 m pipe lattice. Keep H aligned."
                    : "Shared duplex pipe for reactor, turbines and coolers. Align H with H and C with C. Cap unused sockets.";
            }
        }

        public static string JointHint(ThermalJointStatus status)
        {
            switch (status)
            {
                case ThermalJointStatus.Matched: return "Aligned";
                case ThermalJointStatus.Facing: return "Turn the socket faces toward each other";
                case ThermalJointStatus.Roll: return "Rotate around the socket axis: H must meet H";
                case ThermalJointStatus.Crowded: return "Overlapping sockets: one peer per socket";
                default: return "Connect or cap this socket";
            }
        }

        public static ThermalBuildCheck Inspect(IList<ThermalEndpoint> blocks, long selected)
        {
            var result = new ThermalBuildCheck();
            // Include unfinished/off blocks in the geometry graph. Remember
            // their actual build state separately and never modify the inputs.
            var geometry = new List<ThermalEndpoint>();
            var health = new Dictionary<long, bool>();
            ThermalEndpoint anchor = null;
            foreach (var node in blocks)
            {
                var copy = new ThermalEndpoint { Id = node.Id, GridId = node.GridId,
                    Model = node.Model, Ports = node.Ports, Healthy = true };
                geometry.Add(copy); health[node.Id] = node.Healthy;
                if (copy.Id == selected) anchor = copy;
            }
            var network = new ThermalNetwork(geometry);
            var component = network.PhysicalComponent(anchor);
            int sources = 0;
            foreach (var node in component)
            {
                result.Nodes.Add(node);
                if (!health[node.Id]) result.Pending++;
                if (node.Model.Kind == ThermalKind.Reactor) { sources++; result.Source = node; }
                if (node.Model.Kind == ThermalKind.Train) result.Trains++;
            }
            foreach (var joint in network.Joints)
            {
                if (!component.Contains(joint.Node)) continue;
                result.Joints.Add(joint);
                if (joint.Status == ThermalJointStatus.Open) result.Open++;
                else if (joint.Status != ThermalJointStatus.Matched) result.Wrong++;
            }
            if (anchor == null) result.Next = "Select a thermal block";
            else if (result.Wrong > 0) result.Next = "Fix red joints: match facing and H/C roll";
            else if (result.Open > 0) result.Next = "Connect or cap " + result.Open + " open socket(s); use reactor adapters at the housing";
            else if (sources != 1) result.Next = sources == 0 ? "Connect this assembly to one reactor through the shared duplex network" : "Separate supplies: one reactor per plant";
            else
            {
                var plant = network.Plant(result.Source);
                foreach (var node in plant.Nodes)
                {
                    if (node.Model.Kind == ThermalKind.AirCooler || node.Model.Kind == ThermalKind.Radiator) result.Cooling++;
                }
                if (!plant.Ready) result.Next = plant.Diagnostic;
                else if (result.Cooling == 0) result.Next = "Connect an atmospheric cooler or exposed space radiator to the shared network";
                else if (result.Pending > 0) result.Next = "Weld/repair " + result.Pending + " unfinished or unavailable block(s)";
                else { result.Verified = true; result.Next = "Construction verified. Check deployment, cooling and startup power on the reactor before starting."; }
            }
            foreach (var node in result.Nodes) node.Healthy = health[node.Id];
            return result;
        }

        public static int Matches(ThermalEndpoint candidate, IList<ThermalEndpoint> blocks)
        {
            int count = 0;
            foreach (var port in candidate.Ports)
            {
                int peers = 0; bool aligned = false;
                foreach (var block in blocks)
                    if (block.GridId == candidate.GridId && block.Id != candidate.Id)
                        foreach (var other in block.Ports)
                            if (Vector3.DistanceSquared(port.Position, other.Position) <= .00000001f)
                            { peers++; aligned = ThermalNetwork.Match(candidate, port, block, other) == ThermalJointStatus.Matched; }
                if (peers == 1 && aligned) count++;
            }
            return count;
        }

        public static Matrix Suggest(ThermalEndpoint candidate, Matrix current, Vector3 centre, IList<ThermalEndpoint> blocks)
        {
            Matrix best = current;
            int score = Matches(candidate, blocks);
            var axes = new[] { Vector3.UnitX, -Vector3.UnitX, Vector3.UnitY, -Vector3.UnitY, Vector3.UnitZ, -Vector3.UnitZ };
            foreach (var forward in axes)
                foreach (var up in axes)
                {
                    if (Math.Abs(Vector3.Dot(forward, up)) > .01) continue;
                    Matrix rotation = Matrix.CreateWorld(Vector3.Zero, forward, up);
                    var pose = ThermalEndpoint.At(candidate.Id, candidate.GridId, candidate.Model, rotation, centre, false);
                    int matched = Matches(pose, blocks);
                    if (matched > score) { score = matched; best = rotation; }
                }
            return best;
        }
    }
}
