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

    public enum ThermalJointStatus { Open, Matched, Circuit, Facing, Roll, Crowded }

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
        private readonly Dictionary<string, Dictionary<ThermalEndpoint, ThermalCircuit>> circuits
            = new Dictionary<string, Dictionary<ThermalEndpoint, ThermalCircuit>>();
        private readonly Dictionary<string, Dictionary<ThermalEndpoint, List<ThermalEndpoint>>> links
            = new Dictionary<string, Dictionary<ThermalEndpoint, List<ThermalEndpoint>>>();

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
            if (p.Circuit != q.Circuit) return ThermalJointStatus.Circuit;
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
            foreach (string type in new[] { "PRIMARY", "CO2_HP", "CO2_LP" })
            {
                var adjacent = new Dictionary<ThermalEndpoint, List<ThermalEndpoint>>();
                var open = new HashSet<ThermalEndpoint>(brokenSockets);
                foreach (var node in nodes)
                    if (node.Healthy)
                        foreach (var port in node.Ports)
                            if (port.Circuit == type) { adjacent[node] = new List<ThermalEndpoint>(); break; }
                foreach (var grid in grids.Values)
                    foreach (var sockets in grid.Values)
                        foreach (var a in sockets)
                        {
                            if (!a.Node.Healthy || a.Port.Circuit != type) continue;
                            Socket b = sockets.Count == 2 ? sockets[a == sockets[0] ? 1 : 0] : null;
                            if (!Mates(a, b))
                                open.Add(a.Node);
                            // An intact but failed/off machine closes its valves.
                            // Missing pipes/blocks still leave an open circuit.
                            else if (b.Node.Healthy) adjacent[a.Node].Add(b.Node);
                        }
                var groups = new Dictionary<ThermalEndpoint, ThermalCircuit>();
                foreach (var start in adjacent.Keys)
                {
                    if (groups.ContainsKey(start)) continue;
                    var group = new ThermalCircuit();
                    var queue = new Queue<ThermalEndpoint>();
                    queue.Enqueue(start); groups[start] = group;
                    while (queue.Count > 0)
                    {
                        var node = queue.Dequeue(); group.Nodes.Add(node);
                        if (open.Contains(node)) group.Closed = false;
                        foreach (var next in adjacent[node])
                            if (!groups.ContainsKey(next)) { groups[next] = group; queue.Enqueue(next); }
                    }
                }
                circuits[type] = groups;
                links[type] = adjacent;
            }
        }

        // Construction follows coincident joints even when their type/roll is
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

        public ThermalCircuit Circuit(ThermalEndpoint node, string type)
        {
            Dictionary<ThermalEndpoint, ThermalCircuit> groups;
            ThermalCircuit result;
            return circuits.TryGetValue(type, out groups) && groups.TryGetValue(node, out result) ? result : null;
        }

        public ThermalConnections Plant(ThermalEndpoint reactor)
        {
            var result = new ThermalConnections();
            var primary = Circuit(reactor, "PRIMARY");
            if (primary == null || !primary.Closed) { result.Diagnostic = "Seal and connect every PRIMARY socket, including unused manifold ports"; return result; }
            ThermalCircuit hp = null, lp = null;
            int sources = 0, heaters = 0;
            foreach (var node in primary.Nodes)
            {
                if (node.Model.Kind == ThermalKind.Reactor) sources++;
                if (node.Model.Kind != ThermalKind.Heater) continue;
                heaters++;
                var group = Circuit(node, "CO2_HP");
                if (hp != null && hp != group) { result.Diagnostic = "Prototype requires one connected HP bank per reactor"; return result; }
                hp = group;
            }
            if (sources != 1) { result.Diagnostic = "Isolate PRIMARY supplies: one reactor per runtime prototype plant"; return result; }
            if (heaters == 0 || hp == null || !hp.Closed) { result.Diagnostic = "Connect a heater and seal the CO2 HP circuit"; return result; }
            int trains = 0;
            foreach (var node in hp.Nodes)
            {
                if (node.Model.Kind == ThermalKind.Heater && !primary.Nodes.Contains(node))
                { result.Diagnostic = "Shared HP bank reaches another PRIMARY supply"; return result; }
                if (node.Model.Kind != ThermalKind.Train) continue;
                trains++;
                var group = Circuit(node, "CO2_LP");
                if (lp != null && lp != group) { result.Diagnostic = "All connected trains require the same closed LP/cooling bank"; return result; }
                lp = group;
            }
            if (trains == 0 || lp == null || !lp.Closed) { result.Diagnostic = "Connect a train and seal its CO2 LP/cooling route"; return result; }
            foreach (var node in lp.Nodes)
                if (node.Model.Kind == ThermalKind.Train && !hp.Nodes.Contains(node))
                { result.Diagnostic = "Shared LP bank reaches another HP bank"; return result; }
            foreach (var node in primary.Nodes) if (!result.Nodes.Contains(node)) result.Nodes.Add(node);
            foreach (var node in hp.Nodes) if (!result.Nodes.Contains(node)) result.Nodes.Add(node);
            foreach (var node in lp.Nodes) if (!result.Nodes.Contains(node)) result.Nodes.Add(node);
            // A recovery machine earns credit only when both of its physically
            // separate pressure legs belong to this same plant.
            var hotRecovery = RoutedNodes(hp, "CO2_HP", ThermalKind.Heater, ThermalKind.Train);
            var coldRecovery = RoutedNodes(lp, "CO2_LP", ThermalKind.Train, ThermalKind.AirCooler);
            coldRecovery.UnionWith(RoutedNodes(lp, "CO2_LP", ThermalKind.Train, ThermalKind.Radiator));
            result.Nodes.RemoveAll(n => n.Model.Kind == ThermalKind.Recuperator
                && (Circuit(n, "CO2_HP") != hp || Circuit(n, "CO2_LP") != lp
                    || !hotRecovery.Contains(n) || !coldRecovery.Contains(n)));
            return result;
        }

        // Orient only shortest physical routes between dispatched sources and sinks.
        // Capped spurs and standby-machine branches carry no cosmetic flow.
        public Dictionary<long, byte[]> FlowDirections(string type, HashSet<long> from, HashSet<long> to)
        {
            var result = new Dictionary<long, byte[]>();
            Dictionary<ThermalEndpoint, List<ThermalEndpoint>> adjacent;
            if (!links.TryGetValue(type, out adjacent)) return result;
            var edges = new Dictionary<ThermalEndpoint, HashSet<ThermalEndpoint>>();
            foreach (var node in adjacent.Keys) edges[node] = new HashSet<ThermalEndpoint>();
            foreach (var start in adjacent.Keys)
            {
                var circuit = Circuit(start, type);
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
                if (joint.Status != ThermalJointStatus.Matched || joint.Port.Circuit != type) continue;
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

        private HashSet<ThermalEndpoint> RoutedNodes(ThermalCircuit circuit, string type, ThermalKind from, ThermalKind to)
        {
            // Credit machines on shortest physical routes, including equal
            // parallel routes. A sealed dead-end recovery decoration earns no
            // efficiency. Complex unequal recovery loops remain conservative.
            var result = new HashSet<ThermalEndpoint>();
            foreach (var start in circuit.Nodes)
            {
                if (start.Model.Kind != from) continue;
                var distance = new Dictionary<ThermalEndpoint, int> { { start, 0 } };
                var queue = new Queue<ThermalEndpoint>(); queue.Enqueue(start);
                while (queue.Count > 0)
                {
                    var node = queue.Dequeue();
                    foreach (var next in links[type][node])
                        if (!distance.ContainsKey(next)) { distance[next] = distance[node] + 1; queue.Enqueue(next); }
                }
                foreach (var end in circuit.Nodes)
                {
                    if (end.Model.Kind != to || !distance.ContainsKey(end)) continue;
                    var visited = new HashSet<ThermalEndpoint> { end };
                    queue.Enqueue(end);
                    while (queue.Count > 0)
                    {
                        var node = queue.Dequeue(); result.Add(node);
                        foreach (var next in links[type][node])
                            if (distance[next] == distance[node] - 1 && visited.Add(next)) queue.Enqueue(next);
                    }
                }
            }
            return result;
        }
    }
}
