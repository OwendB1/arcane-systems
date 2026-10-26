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
                && check != null && (!check.Verified || state.Faulted || state.ConnectedLoops == 0);
        }

        public static string Role(ThermalModel model)
        {
            switch (model.Kind)
            {
                case ThermalKind.Reactor: return "Four independent manifold circuits; one turbine and cooling per circuit. Each supplies up to 25% capacity. Unused reactor manifolds stay closed. Stop/cool before changing mode.";
                case ThermalKind.Train: return "One lower-cell duplex H/C socket on a 2x2x5 train. Use exactly one turbine plus cooling per reactor manifold circuit. Keep the four circuits separate. Its built-in compressor needs grid power for startup and hot shutdown circulation.";
                case ThermalKind.RadiatorPanel: return "Stack above the base or first panel on the same grid. Centre the shaft and match Up; any yaw works. Up to two extensions share the base's axis and cooling loop.";
                case ThermalKind.AirCooler: return "Connect the rear cooling socket. Mount casing flush in hull; keep 2.5 m clear beyond both front fan guards. Blocked exhaust stops cooling; needs atmosphere and circulation.";
                case ThermalKind.Radiator: return "Connect cooling underneath the pedestal. Panels automatically track edge-on to the sun; keep both faces open to space and the 3x3x3 sweep clear. Red glow shows heat dissipation.";
                default: return model.Subtype.EndsWith("ReactorAdapter") || model.Subtype.EndsWith("ReactorAdapterBare")
                    ? "Offset inlet connects only to the reactor vessel; the opposite end connects to normal pipes. Bridge the 170 mm socket offset and keep H aligned."
                    : "Duplex H/C pipe within one manifold circuit. Align H with H and C with C. Seal unused junction mouths with end caps. A breach closes that circuit at the reactor.";
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
                case ThermalJointStatus.ReactorOnly: return "This adapter end connects only to the reactor vessel; use the opposite end for pipes";
                default: return "Reactor manifold stays closed; cap open pipe mouths or reconnect";
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
                if (anchor != null && anchor.Model.Kind != ThermalKind.Reactor && joint.Node.Model.Kind == ThermalKind.Reactor
                    && !network.Joints.Exists(other => other.Node != joint.Node && component.Contains(other.Node)
                        && Vector3.DistanceSquared(other.Port.Position, joint.Port.Position) <= .00000001f)) continue;
                if (joint.Status == ThermalJointStatus.Open) result.Open++;
                // Keep both ends for highlighting, but count each faulty joint once.
                else if (joint.Status != ThermalJointStatus.Matched && !result.Joints.Exists(other =>
                    other.Status != ThermalJointStatus.Open && other.Status != ThermalJointStatus.Matched
                    && other.Node.GridId == joint.Node.GridId
                    && Vector3.DistanceSquared(other.Port.Position, joint.Port.Position) <= .00000001f)) result.Wrong++;
                result.Joints.Add(joint);
            }
            if (anchor == null) result.Next = "Select a thermal block";
            else if (result.Wrong > 0)
            {
                var mismatch = result.Joints.Find(j => j.Status != ThermalJointStatus.Open && j.Status != ThermalJointStatus.Matched);
                result.Next = result.Wrong + (result.Wrong == 1 ? " mismatched connection: " : " mismatched connections: ")
                    + JointHint(mismatch.Status);
            }
            else if (sources != 1) result.Next = sources == 0 ? "Connect this circuit to one reactor manifold" : "Separate reactor supplies";
            else
            {
                var plant = network.Plant(result.Source);
                var circuits = network.Loops(result.Source);
                string fault = null;
                int ready = 0;
                for (int i = 0; i < circuits.Length; i++)
                {
                    var joint = result.Joints.Find(j => j.Node == result.Source && j.Port == result.Source.Ports[i]);
                    if (joint == null) continue;
                    if (circuits[i].Ready) ready++;
                    else
                    {
                        // An unused root is safe. An attached incomplete/breached
                        // circuit must remain visible even when peers can operate.
                        if (joint.Peer != null) fault = "Circuit " + (i + 1) + ": " + circuits[i].Diagnostic;
                    }
                }
                foreach (var node in plant.Nodes)
                {
                    if (component.Contains(node) && (node.Model.Kind == ThermalKind.AirCooler || node.Model.Kind == ThermalKind.Radiator)) result.Cooling++;
                }
                if (fault != null) result.Next = fault;
                else if (!plant.Ready) result.Next = plant.Diagnostic;
                else if (result.Cooling == 0) result.Next = "Connect cooling within this manifold circuit";
                else if (result.Pending > 0) result.Next = "Weld/repair " + result.Pending + " unfinished or unavailable block(s)";
                else { result.Verified = true; result.Next = ready + "/4 circuit layouts verified. See Server below for operating readiness."; }
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
