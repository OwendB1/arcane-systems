using System;
using System.Collections.Generic;
using VRageMath;

namespace ArcanePower
{
    public sealed class ThermalPort
    {
        public string Circuit;
        public Vector3 Position, Normal, HotAxis;
        public ThermalPort(string circuit, Vector3 position, Vector3 normal, Vector3 hotAxis)
        { Circuit = circuit; Position = position; Normal = normal; HotAxis = hotAxis; }
    }

    public sealed class ThermalModel
    {
        public string Subtype;
        public Vector3I Cells;
        public ThermalKind Kind;
        public int Grade;
        public double RatingMW;
        public ThermalPort[] Ports;
        public double CapacityMJ { get { return RatingMW * 8; } }
    }

    public sealed class ThermalEndpoint
    {
        public long Id, GridId;
        public bool Healthy;
        public ThermalModel Model;
        public ThermalPort[] Ports;

        public static ThermalEndpoint At(long id, long gridId, ThermalModel model, Matrix rotation, Vector3 centre, bool healthy)
        {
            var ports = new ThermalPort[model.Ports.Length];
            for (int i = 0; i < ports.Length; i++)
            {
                var p = model.Ports[i];
                ports[i] = new ThermalPort(p.Circuit, Vector3.Transform(p.Position, rotation) + centre,
                    Vector3.TransformNormal(p.Normal, rotation), Vector3.TransformNormal(p.HotAxis, rotation));
            }
            return new ThermalEndpoint { Id = id, GridId = gridId, Model = model, Ports = ports, Healthy = healthy };
        }
    }

    public enum ThermalJointStatus { Open, Matched, Facing, Roll, Crowded }

    public sealed class ThermalJoint
    {
        public ThermalEndpoint Node, Peer;
        public ThermalPort Port;
        public ThermalJointStatus Status;
    }

    public sealed class ThermalCircuit
    {
        public bool Closed = true;
        public readonly List<ThermalEndpoint> Nodes = new List<ThermalEndpoint>();
    }

    public sealed class ThermalConnections
    {
        public string Diagnostic;
        public readonly List<ThermalEndpoint> Nodes = new List<ThermalEndpoint>();
        public bool Ready { get { return Diagnostic == null; } }
    }

    // Socket positions are measured in grid-local metres, never rounded world
    // coordinates. The 170 mm reactor adapter is part of the authored contract.
    public sealed class ThermalNetwork
    {
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
        private readonly Dictionary<ThermalEndpoint, ThermalCircuit> circuits
            = new Dictionary<ThermalEndpoint, ThermalCircuit>();
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
            var brokenSockets = new HashSet<ThermalEndpoint>();
            foreach (var grid in grids.Values)
            {
                socketGroups.AddRange(grid.Values);
                foreach (var sockets in grid.Values)
                    foreach (var a in sockets)
                    {
                        Socket b = sockets.Count == 2 ? sockets[a == sockets[0] ? 1 : 0] : null;
                        if (!Mates(a, b)) brokenSockets.Add(a.Node);
                    }
            }
            // All sockets carry the same paired supply/return channels. A train
            // has one socket, so only fittings can branch the shared network.
            foreach (var node in nodes)
                if (node.Healthy && node.Ports.Length > 0) links[node] = new List<ThermalEndpoint>();
            foreach (var sockets in socketGroups)
                foreach (var a in sockets)
                {
                    if (!a.Node.Healthy) continue;
                    Socket b = sockets.Count == 2 ? sockets[a == sockets[0] ? 1 : 0] : null;
                    // Intact disabled machines close their valves. Missing or
                    // misaligned connections still leave the network open.
                    if (Mates(a, b) && b.Node.Healthy) links[a.Node].Add(b.Node);
                }
            foreach (var start in links.Keys)
            {
                if (circuits.ContainsKey(start)) continue;
                var group = new ThermalCircuit();
                var queue = new Queue<ThermalEndpoint>();
                queue.Enqueue(start); circuits[start] = group;
                while (queue.Count > 0)
                {
                    var node = queue.Dequeue(); group.Nodes.Add(node);
                    if (brokenSockets.Contains(node)) group.Closed = false;
                    foreach (var next in links[node])
                        if (!circuits.ContainsKey(next)) { circuits[next] = group; queue.Enqueue(next); }
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
                foreach (var next in physical[queue.Dequeue()])
                    if (result.Add(next)) queue.Enqueue(next);
            return result;
        }

        public ThermalCircuit Circuit(ThermalEndpoint node)
        {
            ThermalCircuit result;
            return circuits.TryGetValue(node, out result) ? result : null;
        }

        public ThermalConnections Plant(ThermalEndpoint reactor)
        {
            var result = new ThermalConnections();
            var circuit = Circuit(reactor);
            if (circuit == null || !circuit.Closed)
            { result.Diagnostic = "Connect the shared duplex network, align H/C and cap unused sockets"; return result; }
            int sources = 0, trains = 0, coolers = 0;
            foreach (var node in circuit.Nodes)
            {
                if (node.Model.Kind == ThermalKind.Reactor) sources++;
                if (node.Model.Kind == ThermalKind.Train) trains++;
                if (node.Model.Kind == ThermalKind.AirCooler || node.Model.Kind == ThermalKind.Radiator) coolers++;
            }
            if (sources != 1) { result.Diagnostic = "Separate supplies: one reactor per plant"; return result; }
            if (trains == 0) { result.Diagnostic = "Connect a turbine to the shared pipe network"; return result; }
            if (coolers == 0) { result.Diagnostic = "Connect an atmospheric cooler or space radiator to the shared network"; return result; }
            result.Nodes.AddRange(circuit.Nodes);
            return result;
        }

        // Orient only shortest physical routes between dispatched sources and sinks.
        // Capped spurs and standby-machine branches carry no cosmetic flow.
        public Dictionary<long, byte[]> FlowDirections(HashSet<long> from, HashSet<long> to)
        {
            var result = new Dictionary<long, byte[]>();
            var adjacent = links;
            var edges = new Dictionary<ThermalEndpoint, HashSet<ThermalEndpoint>>();
            foreach (var node in adjacent.Keys) edges[node] = new HashSet<ThermalEndpoint>();
            foreach (var start in adjacent.Keys)
            {
                var circuit = Circuit(start);
                if (!from.Contains(start.Id) || circuit == null || !circuit.Closed) continue;
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
