using System;
using System.Collections.Generic;
using VRageMath;

namespace ArcanePower
{
    public sealed class ThermalPort
    {
        public string Circuit;
        public Vector3 Position, Normal, HotAxis;
        public bool ReactorOnly;
        public ThermalPort(string circuit, Vector3 position, Vector3 normal, Vector3 hotAxis, bool reactorOnly = false)
        { Circuit = circuit; Position = position; Normal = normal; HotAxis = hotAxis; ReactorOnly = reactorOnly; }
    }

    public sealed class ThermalModel
    {
        public string Subtype;
        public Vector3I Cells;
        public ThermalKind Kind;
        public int Grade;
        public double RatingMW, CoolingMW;
        public ThermalPort[] Ports;
        // Keep accepting pre-rebalance saved heat; admission and dispatch use RatingMW.
        public double CapacityMJ
        {
            get { return (Kind == ThermalKind.Reactor || (Kind == ThermalKind.Train && Grade == 3)
                ? 2500000 : Kind == ThermalKind.Train ? 25000 : RatingMW) * 8; }
        }
    }

    public sealed class ThermalEndpoint
    {
        public long Id, GridId;
        public bool Healthy;
        public int Revision;
        public ThermalModel Model;
        public ThermalPort[] Ports;

        public static ThermalEndpoint At(long id, long gridId, ThermalModel model, Matrix rotation, Vector3 centre, bool healthy)
        {
            var ports = new ThermalPort[model.Ports.Length];
            for (int i = 0; i < ports.Length; i++)
            {
                var p = model.Ports[i];
                ports[i] = new ThermalPort(p.Circuit, Vector3.Transform(p.Position, rotation) + centre,
                    Vector3.TransformNormal(p.Normal, rotation), Vector3.TransformNormal(p.HotAxis, rotation), p.ReactorOnly);
            }
            return new ThermalEndpoint { Id = id, GridId = gridId, Model = model, Ports = ports, Healthy = healthy };
        }
    }

    public enum ThermalJointStatus { Open, Matched, Facing, Roll, Crowded, ReactorOnly }

    public sealed class ThermalJoint
    {
        public ThermalEndpoint Node, Peer;
        public ThermalPort Port;
        public ThermalJointStatus Status;
    }

    public sealed class ThermalConnections
    {
        public string Diagnostic;
        public readonly List<ThermalEndpoint> Nodes = new List<ThermalEndpoint>();
        public bool Ready { get { return Diagnostic == null; } }
    }

    // Circuit validity belongs to the physical assembly, independently of Start.
    // Copy the inputs so later health/placement changes cannot mutate the cache.
    public sealed class ThermalCircuitCache
    {
        public readonly List<ThermalEndpoint> Nodes = new List<ThermalEndpoint>();
        public readonly ThermalNetwork Network;
        public readonly ThermalConnections[] Circuits;
        public bool Invalidated;

        public ThermalCircuitCache(IList<ThermalEndpoint> nodes)
        {
            foreach (var node in nodes)
            {
                var ports = new ThermalPort[node.Ports.Length];
                for (int i = 0; i < ports.Length; i++)
                {
                    var port = node.Ports[i];
                    ports[i] = new ThermalPort(port.Circuit, port.Position, port.Normal, port.HotAxis, port.ReactorOnly);
                }
                Nodes.Add(new ThermalEndpoint { Id = node.Id, GridId = node.GridId,
                    Healthy = node.Healthy, Revision = node.Revision, Model = node.Model, Ports = ports });
            }
            Network = new ThermalNetwork(Nodes);
            Circuits = Network.Loops(Nodes[0]);
        }

        public bool Matches(IList<ThermalEndpoint> nodes)
        {
            if (Invalidated || nodes.Count != Nodes.Count) return false;
            for (int i = 0; i < nodes.Count; i++)
                if (!Same(nodes[i], Nodes[i])) return false;
            return true;
        }

        public bool CircuitChanged(ThermalCircuitCache previous, int index)
        {
            if (previous == null || index >= previous.Circuits.Length) return true;
            var before = previous.Circuits[index]; var after = Circuits[index];
            if (before.Ready != after.Ready || before.Nodes.Count != after.Nodes.Count) return true;
            foreach (var node in after.Nodes)
                if (!Same(node, before.Nodes.Find(old => old.Id == node.Id))) return true;
            return false;
        }

        private static bool Same(ThermalEndpoint a, ThermalEndpoint b)
        {
            if (a == null || b == null || a.Id != b.Id || a.GridId != b.GridId || a.Healthy != b.Healthy
                || a.Revision != b.Revision || a.Model != b.Model || a.Ports.Length != b.Ports.Length) return false;
            for (int j = 0; j < a.Ports.Length; j++)
            {
                var p = a.Ports[j]; var q = b.Ports[j];
                if (p.Circuit != q.Circuit || p.Position != q.Position || p.Normal != q.Normal
                    || p.HotAxis != q.HotAxis || p.ReactorOnly != q.ReactorOnly) return false;
            }
            return true;
        }
    }

    // Socket positions are measured in grid-local metres, never rounded world
    // coordinates. The 170 mm reactor adapter is part of the authored contract.
    public sealed class ThermalNetwork
    {
        private readonly Dictionary<ThermalEndpoint, byte> openPorts = new Dictionary<ThermalEndpoint, byte>();
        public byte OpenPorts(ThermalEndpoint node) { byte mask; return openPorts.TryGetValue(node, out mask) ? mask : (byte)0; }

        private readonly List<List<Socket>> socketGroups = new List<List<Socket>>();
        private List<ThermalJoint> joints;
        private Dictionary<ThermalEndpoint, List<ThermalEndpoint>> physical;
        public List<ThermalJoint> Joints
        {
            get
            {
                if (joints != null) return joints;
                // Only construction inspection needs per-socket diagnostics.
                // Keep these allocations out of server dispatch's frame loop.
                joints = new List<ThermalJoint>();
                physical = new Dictionary<ThermalEndpoint, List<ThermalEndpoint>>();
                foreach (var sockets in socketGroups)
                    foreach (var a in sockets)
                    {
                        Socket b = sockets.Count == 2 ? sockets[a == sockets[0] ? 1 : 0] : null;
                        joints.Add(new ThermalJoint { Node = a.Node, Port = a.Port, Peer = b == null ? null : b.Node,
                            Status = sockets.Count > 2 ? ThermalJointStatus.Crowded
                                : b == null ? ThermalJointStatus.Open : Match(a.Node, a.Port, b.Node, b.Port) });
                        List<ThermalEndpoint> peers;
                        if (!physical.TryGetValue(a.Node, out peers)) physical[a.Node] = peers = new List<ThermalEndpoint>();
                        foreach (var other in sockets)
                            if (other.Node != a.Node && !peers.Contains(other.Node)) peers.Add(other.Node);
                    }
                return joints;
            }
        }
        private readonly Dictionary<ThermalEndpoint, List<ThermalEndpoint>> links
            = new Dictionary<ThermalEndpoint, List<ThermalEndpoint>>();

        private sealed class Socket
        {
            internal ThermalEndpoint Node;
            internal ThermalPort Port;
        }

        public static ThermalJointStatus Match(ThermalEndpoint a, ThermalPort p, ThermalEndpoint b, ThermalPort q)
        {
            if (a == null || b == null || p == null || q == null || a == b || a.GridId != b.GridId
                || !(Vector3.DistanceSquared(p.Position, q.Position) <= .00000001f))
                return ThermalJointStatus.Open;
            if (!(Vector3.Dot(p.Normal, q.Normal) <= -.9999f)) return ThermalJointStatus.Facing;
            if (!(Vector3.Dot(p.HotAxis, q.HotAxis) >= .9999f)) return ThermalJointStatus.Roll;
            if ((p.ReactorOnly && (b.Model == null || b.Model.Kind != ThermalKind.Reactor))
                || (q.ReactorOnly && (a.Model == null || a.Model.Kind != ThermalKind.Reactor))) return ThermalJointStatus.ReactorOnly;
            return ThermalJointStatus.Matched;
        }

        private static bool Mates(Socket a, Socket b)
        { return b != null && Match(a.Node, a.Port, b.Node, b.Port) == ThermalJointStatus.Matched; }

        public ThermalNetwork(IList<ThermalEndpoint> nodes)
        {
            var grids = new Dictionary<long, Dictionary<Vector3I, List<Socket>>>();
            foreach (var node in nodes)
            {
                Dictionary<Vector3I, List<Socket>> grid;
                if (!grids.TryGetValue(node.GridId, out grid)) grids[node.GridId] = grid = new Dictionary<Vector3I, List<Socket>>();
                foreach (var port in node.Ports)
                {
                    var point = new Vector3I((int)Math.Round(port.Position.X * 1000), (int)Math.Round(port.Position.Y * 1000), (int)Math.Round(port.Position.Z * 1000));
                    List<Socket> sockets;
                    if (!grid.TryGetValue(point, out sockets)) grid[point] = sockets = new List<Socket>();
                    sockets.Add(new Socket { Node = node, Port = port });
                }
            }
            foreach (var grid in grids.Values) socketGroups.AddRange(grid.Values);
            // Build the raw paired-channel graph. Loops() treats the reactor as
            // separate roots, so its four ports cannot bridge circuits.
            foreach (var node in nodes)
                if (node.Healthy && node.Ports.Length > 0) links[node] = new List<ThermalEndpoint>();
            foreach (var sockets in socketGroups)
                foreach (var a in sockets)
                {
                    if (!a.Node.Healthy) continue;
                    Socket b = sockets.Count == 2 ? sockets[a == sockets[0] ? 1 : 0] : null;
                    // This mask describes valid joints, not automatic pipe caps.
                    // Loops() rejects breaches; reactor valves own isolation.
                    if (Mates(a, b) && b.Node.Healthy)
                    {
                        links[a.Node].Add(b.Node);
                        openPorts[a.Node] = (byte)(OpenPorts(a.Node) | (1 << Array.IndexOf(a.Node.Ports, a.Port)));
                    }
                }
        }

        // Construction follows coincident joints even when their facing/roll is
        // wrong, so a bad joint doesn't hide the rest of the assembly's faults.
        public HashSet<ThermalEndpoint> PhysicalComponent(ThermalEndpoint start)
        {
            var result = new HashSet<ThermalEndpoint>();
            if (Joints.Count == 0) return result;
            if (start == null || !physical.ContainsKey(start)) return result;
            var queue = new Queue<ThermalEndpoint>();
            result.Add(start); queue.Enqueue(start);
            while (queue.Count > 0)
            {
                var node = queue.Dequeue();
                // Inspect one circuit when aiming at its pipes/machines. The
                // selected vessel itself may inspect all four attached circuits.
                if (node != start && node.Model.Kind == ThermalKind.Reactor) continue;
                foreach (var next in physical[node])
                    if (result.Add(next)) queue.Enqueue(next);
            }
            return result;
        }

        // The reactor is a heat source, not a hydraulic bridge between its ports.
        public ThermalConnections[] Loops(ThermalEndpoint reactor)
        {
            var result = new ThermalConnections[reactor.Ports.Length];
            for (int i = 0; i < result.Length; i++)
            {
                var loop = result[i] = new ThermalConnections();
                var joint = Joints.Find(j => j.Node == reactor && j.Port == reactor.Ports[i]);
                if (!reactor.Healthy)
                { loop.Diagnostic = "Reactor unavailable: check build, ownership and manifold deployment"; continue; }
                if (joint == null || joint.Status != ThermalJointStatus.Matched || joint.Peer == null)
                { loop.Diagnostic = "Connect a sealed circuit to this manifold; align H/C"; continue; }
                if (!joint.Peer.Healthy)
                { loop.Diagnostic = "Reactor adapter unavailable: weld, enable and check access"; continue; }
                var found = new HashSet<ThermalEndpoint>();
                var queue = new Queue<ThermalEndpoint>();
                found.Add(joint.Peer); queue.Enqueue(joint.Peer);
                bool otherSource = false;
                while (queue.Count > 0)
                {
                    var node = queue.Dequeue();
                    if (node.Model.Kind == ThermalKind.Reactor) { otherSource = true; continue; }
                    foreach (var next in links[node])
                    {
                        if (next == reactor) continue;
                        if (found.Add(next)) queue.Enqueue(next);
                    }
                }
                int rootPorts = 0, trains = 0, coolers = 0;
                foreach (var root in Joints)
                    if (root.Node == reactor && root.Status == ThermalJointStatus.Matched && found.Contains(root.Peer)) rootPorts++;
                bool sealedCircuit = true;
                foreach (var node in found)
                {
                    if (OpenPorts(node) != (1 << node.Ports.Length) - 1) sealedCircuit = false;
                    if (node.Model.Kind == ThermalKind.Train) trains++;
                    if (node.Model.Kind == ThermalKind.AirCooler || node.Model.Kind == ThermalKind.Radiator) coolers++;
                }
                if (otherSource) loop.Diagnostic = "Separate reactor supplies";
                else if (rootPorts != 1) loop.Diagnostic = "Separate manifold circuits: two reactor outlets are cross-connected";
                else if (!sealedCircuit) loop.Diagnostic = "Circuit breached: repair pipes/H/C alignment and cap unused mouths";
                else if (trains != 1) loop.Diagnostic = "Connect exactly one turbine to this manifold circuit";
                else if (coolers == 0) loop.Diagnostic = "Connect cooling to this manifold circuit";
                if (!loop.Ready) continue;
                loop.Nodes.Add(reactor);
                loop.Nodes.AddRange(found);
            }
            return result;
        }

        public ThermalConnections Plant(ThermalEndpoint reactor)
        {
            var result = new ThermalConnections();
            var added = new HashSet<ThermalEndpoint>();
            string diagnostic = "Connect an independent turbine/cooling circuit";
            foreach (var loop in Loops(reactor))
            {
                if (!loop.Ready) { diagnostic = loop.Diagnostic; continue; }
                foreach (var node in loop.Nodes) if (added.Add(node)) result.Nodes.Add(node);
            }
            if (result.Nodes.Count == 0) result.Diagnostic = diagnostic;
            return result;
        }

        // Orient only shortest physical routes between dispatched sources and sinks.
        // Capped spurs and unselected terminals carry no cosmetic flow.
        public Dictionary<long, byte[]> FlowDirections(HashSet<long> from, HashSet<long> to)
        {
            var result = new Dictionary<long, byte[]>();
            var adjacent = links;
            var edges = new Dictionary<ThermalEndpoint, HashSet<ThermalEndpoint>>();
            foreach (var node in adjacent.Keys) edges[node] = new HashSet<ThermalEndpoint>();
            foreach (var start in adjacent.Keys)
            {
                if (!from.Contains(start.Id)) continue;
                var distance = new Dictionary<ThermalEndpoint, int> { { start, 0 } };
                var queue = new Queue<ThermalEndpoint>(); queue.Enqueue(start);
                while (queue.Count > 0)
                {
                    var node = queue.Dequeue();
                    foreach (var next in adjacent[node])
                        if (!distance.ContainsKey(next)) { distance[next] = distance[node] + 1; queue.Enqueue(next); }
                }
                foreach (var end in adjacent.Keys)
                {
                    if (!to.Contains(end.Id) || !distance.ContainsKey(end)) continue;
                    var visited = new HashSet<ThermalEndpoint> { end }; queue.Enqueue(end);
                    while (queue.Count > 0)
                    {
                        var node = queue.Dequeue();
                        foreach (var previous in adjacent[node])
                            if (distance[previous] == distance[node] - 1)
                            {
                                edges[previous].Add(node);
                                if (visited.Add(previous)) queue.Enqueue(previous);
                            }
                    }
                }
            }
            foreach (var joint in Joints)
            {
                if (joint.Status != ThermalJointStatus.Matched) continue;
                if (!edges.ContainsKey(joint.Node) || !edges.ContainsKey(joint.Peer)) continue;
                bool outgoing = edges[joint.Node].Contains(joint.Peer);
                bool incoming = edges[joint.Peer].Contains(joint.Node);
                if (outgoing == incoming) continue;
                byte[] ports;
                if (!result.TryGetValue(joint.Node.Id, out ports)) result[joint.Node.Id] = ports = new byte[joint.Node.Ports.Length];
                ports[Array.IndexOf(joint.Node.Ports, joint.Port)] = (byte)(outgoing ? 2 : 1);
            }
            return result;
        }

    }
}
