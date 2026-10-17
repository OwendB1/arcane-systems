using System;
using ProtoBuf;
using VRageMath;

namespace ArcanePower
{
    public enum ThermalFlowMode { Unconnected, Ready, Pumping, Fault }

    // Cosmetic observations of the paid server plant, never a second fluid store.
    [ProtoContract]
    public sealed class ThermalFlowState
    {
        [ProtoMember(1)] public long EntityId;
        [ProtoMember(2)] public long Sequence;
        [ProtoMember(3)] public ThermalFlowMode Mode;
        [ProtoMember(4)] public double Rate;
        [ProtoMember(5)] public double Heat;
        // H direction at each socket: 0 idle, 1 enters block, 2 leaves block.
        // C always travels the opposite way in the same typed duplex connection.
        [ProtoMember(6)] public byte[] Ports;
        [ProtoMember(7)] public bool Internal;

        public bool Valid(int ports)
        {
            if (EntityId == 0 || Sequence < 0 || Mode < ThermalFlowMode.Unconnected || Mode > ThermalFlowMode.Fault
                || !ThermalMath.Finite(Rate) || Rate < 0 || Rate > 1
                || !ThermalMath.Finite(Heat) || Heat < 0 || Heat > 1
                || Ports == null || ports < 0 || ports > 8 || Ports.Length != ports
                || (Mode != ThermalFlowMode.Pumping && Rate != 0)) return false;
            foreach (byte p in Ports) if (p > 2) return false;
            return true;
        }
    }

    public sealed class ThermalFlowPath
    {
        public string Circuit;
        public bool Hot, Internal;
        public int Port;
        public float Radius;
        public Vector3[] Points;
        public float[] Distances;
        public float Length { get { return Distances[Distances.Length - 1]; } }
        public ThermalFlowPath(string circuit, bool hot, int port, float radius, bool inside, Vector3[] points)
        {
            Circuit = circuit; Hot = hot; Port = port; Radius = radius; Internal = inside; Points = points;
            Distances = new float[points.Length];
            for (int i = 1; i < points.Length; i++) Distances[i] = Distances[i - 1] + Vector3.Distance(points[i - 1], points[i]);
        }
        public Vector3 Sample(double metres)
        {
            float at = (float)Math.Max(0, Math.Min(Length, metres));
            int i = 1;
            while (i < Distances.Length - 1 && Distances[i] < at) i++;
            float span = Distances[i] - Distances[i - 1];
            return Vector3.Lerp(Points[i - 1], Points[i], span > .000001f ? (at - Distances[i - 1]) / span : 0);
        }
        public int Direction(ThermalFlowState state)
        {
            if (state == null || state.Mode != ThermalFlowMode.Pumping || state.Rate <= 0) return 0;
            if (Internal) return state.Internal ? 1 : 0;
            if (Port < 0 || Port >= state.Ports.Length) return 0;
            int sign = state.Ports[Port] == 1 ? 1 : state.Ports[Port] == 2 ? -1 : 0;
            return Hot ? sign : -sign;
        }
    }
}
