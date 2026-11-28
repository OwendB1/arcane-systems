using System;
using System.Collections.Generic;
using Sandbox.ModAPI;
using VRage;
using VRageMath;

namespace ArcanePower
{
    public sealed partial class ThermalSession
    {
        // Local inter-mod registration. Only the simulation server can offer a budget.
        private const long PropulsionChannel = 0x41524350524f5001L;
        private readonly SortedDictionary<long, MyTuple<IMyFunctionalBlock, Func<double, double>>> propulsion =
            new SortedDictionary<long, MyTuple<IMyFunctionalBlock, Func<double, double>>>();
        private static readonly ThermalModel Charger = Socket("ArcaneThrusters_RecoveryChargerLG",
            new Vector3(3.75f, 0, 0), Vector3.Right);

        private static readonly ThermalModel OpenDrive = Socket("ArcaneThrusters_DrivePriorityLG",
            new Vector3(-2.5f, 0, 3.75f), Vector3.Backward);
        private static readonly ThermalModel HullDrive = Socket("ArcaneThrusters_DrivePriorityLG_Hull",
            new Vector3(-2.5f, 0, 5f), Vector3.Backward);

        private static ThermalModel ModelFor(string subtype)
        {
            if (subtype == Charger.Subtype) return Charger;
            if (subtype == OpenDrive.Subtype) return OpenDrive;
            return subtype == HullDrive.Subtype ? HullDrive : null;
        }

        private static ThermalModel Socket(string subtype, Vector3 position, Vector3 normal)
        {
            return new ThermalModel { Subtype = subtype, Kind = ThermalKind.Pipe,
                Ports = new[] { new ThermalPort("CO2", position, normal, Vector3.Up) } };
        }

        private void RegisterPropulsion(object message)
        {
            if (!(message is MyTuple<IMyFunctionalBlock, Func<double, double>>)) return;
            var load = (MyTuple<IMyFunctionalBlock, Func<double, double>>)message;
            var block = load.Item1;
            if (block == null || ModelFor(block.BlockDefinition.SubtypeName) == null) return;
            if (load.Item2 == null) propulsion.Remove(block.EntityId);
            else if (!block.MarkedForClose) propulsion[block.EntityId] = load;
        }

        private void AddPropulsionPorts(List<ThermalEndpoint> nodes, HashSet<long> grids, long owner)
        {
            foreach (var entry in propulsion.Values)
            {
                var block = entry.Item1;
                if (block.MarkedForClose || !grids.Contains(block.CubeGrid.EntityId)) continue;
                Matrix rotation;
                block.Orientation.GetMatrix(out rotation);
                var centre = ((VRage.Game.Entity.MyEntity)block).PositionComp.LocalMatrixRef.Translation;
                nodes.Add(ThermalEndpoint.At(block.EntityId, block.CubeGrid.EntityId, ModelFor(block.BlockDefinition.SubtypeName), rotation, centre,
                    block.IsFunctional && block.SlimBlock.BuildLevelRatio >= 1 && block.HasPlayerAccess(owner)));
            }
        }

        private void AllocateDrive(Reactor source, ThermalConnections circuit, ref ThermalOutputGrant grant)
        {
            if (grant == null) return;
            foreach (var endpoint in circuit.Nodes)
            {
                if (endpoint.Model != OpenDrive && endpoint.Model != HullDrive) continue;
                var load = propulsion[endpoint.Id];
                grant = source.DivertPropulsion(grant, load.Item2);
            }
        }

        private void RecoverHeat(ThermalConnections circuit, ThermalLoopState loop)
        {
            foreach (var endpoint in circuit.Nodes)
            {
                if (endpoint.Model != Charger) continue;
                var load = propulsion[endpoint.Id];
                // Reserve before calling the other mod. A failed transfer must never
                // allow the same MJ to be spent on a second charger after an exception.
                double offered = Math.Min(loop.ExcessMJ, 250.0 / 60);
                loop.ExcessMJ -= offered;
                double used = load.Item2(offered);
                if (!ThermalMath.Finite(used) || used < 0 || used > offered)
                    throw new InvalidOperationException("Recovery charger exceeded its heat offer");
                loop.ExcessMJ += offered - used;
                loop.RecoveredMW += used * 60;
            }
        }
    }
}
