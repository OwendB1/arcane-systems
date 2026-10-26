using System.Text;
using System.Collections.Generic;
using Sandbox.Common.ObjectBuilders;
using Sandbox.ModAPI;
using VRage.Game.Components;
using VRage.ObjectBuilders;
using VRage.ModAPI;
using VRage.Game.ModAPI;
using VRage.Utils;
using VRage.Game.Entity;
using VRageMath;
using Sandbox.Game.Lights;

namespace ArcanePower
{
    [MyEntityComponentDescriptor(typeof(MyObjectBuilder_Reactor), false, "ArcanePower_Thermal_ReactorHousing")]
    public sealed partial class Reactor : MyGameLogicComponent
    {
        private IMyReactor reactor;
        private bool closing;
        private bool IsLive
        {
            get
            {
                // SE defers entity deletion. Logic and inventory callbacks can
                // still arrive after creative removal has begun tearing it down.
                return !closing && reactor != null && !reactor.MarkedForClose && !reactor.Closed
                    && reactor.SlimBlock != null && reactor.GetInventory() != null;
            }
        }
        // Native attachment discovery can take several 100-frame passes on load.
        // Wait for real connections, with a deadline for missing/broken hardware,
        // then leave two ticks to prime controller sinks before enforcing power.
        private int initializationFrames = 120;
        private int controllerDiscoveryFrames = 600;
        private int reloadPowerFrames;
        private bool motionInitialized;
        private float previousControllers = -1;
        private int controllerRingCapacity = 2;
        private int previousFuelTier;
        private MyEntitySubpart previousRing;
        private int appearanceRefresh;
        private ReactorStatus previousStatus;
        private bool previousPrecharging, previousThermalWarning;
        private int pulseTick;
        private const float EmissiveIntensity = 12f;
        private MyLight coreGlow;
        internal static readonly Color[] FuelColors = {
            new Color(40, 185, 255), new Color(255, 145, 40), new Color(180, 85, 255)
        };

        public override void Init(MyObjectBuilder_EntityBase builder)
        {
            reactor = (IMyReactor)Entity;
            reactor.AddUpgradeValue("ArcaneContainment", 0f);
            reactor.AddUpgradeValue("ArcaneControllerCount", 0f);
            NeedsUpdate = MyEntityUpdateEnum.BEFORE_NEXT_FRAME;
        }

        public override void UpdateOnceBeforeFrame()
        {
            if (!IsLive) return;
            // Brayton exports through turbines, so the native reactor reports
            // not-working and repeatedly paints its own yellow warning. Our
            // containment/fuel/thermal presentation owns these materials.
            ((Sandbox.Game.Entities.MyCubeBlock)Entity).HandleEmissiveStateChange = false;
            reactor.OnUpgradeValuesChanged += CheckContainment;
            reactor.AppendingCustomInfo += AppendInfo;
            NeedsUpdate = MyEntityUpdateEnum.EACH_FRAME;
            InitializeMotion();
            CheckContainment();
            InitializeFuel();
            InitializeThermalRuntime();
            reactor.EnabledChanged += ThermalEnabledChanged;
        }

        public override void UpdateBeforeSimulation()
        {
            if (!IsLive) return;
            RefreshRestPoses();
            if (initializationFrames > 0)
            {
                CheckContainment();
                if (--controllerDiscoveryFrames > 0 && (previousControllers < 2 || !HasIntactControllers()))
                    initializationFrames = System.Math.Max(initializationFrames, 4);
                if (--initializationFrames > 0)
                {
                    // A restored critical core must keep its independent fuse
                    // even while native controller discovery is pending.
                    if (MyAPIGateway.Multiplayer.IsServer) UpdateCriticalCore();
                    if (initializationFrames <= 2)
                    {
                        CheckVentRoute();
                        UpdateFuel();
                        UpdatePower();
                    }
                    if (!MyAPIGateway.Utilities.IsDedicated)
                    {
                        DrawMotion();
                        DrawVentOutlet();
                    }
                    UpdateAppearance();
                    UpdateSound();
                    return;
                }
                // The thermal session validates circuits and grants paid output
                // after this frame. Bridge the native distributor handoff using
                // the saved containment reserve; never restart a saved Off core.
                if (reactor.Enabled && !Motion.PowerStarved && Motion.Vent == VentPhase.Idle
                    && (Motion.Core == CorePhase.Starting || Motion.Core == CorePhase.Running))
                    reloadPowerFrames = 120;
            }
            // Native module connection events update the value. The enabled guard also
            // catches manual/toolbar attempts to start without the two controllers.
            CheckContainment();
            CheckVentRoute();
            UpdateSafety();
            UpdateFuel();
            UpdatePower();
            UpdateThermalMode();
            UpdateTiles();
            UpdateMotion();
            UpdateAppearance();
            UpdateSound();
        }

        private void CheckContainment()
        {
            if (!IsLive) return;
            float controllers, capacity;
            reactor.UpgradeValues.TryGetValue("ArcaneControllerCount", out controllers);
            reactor.UpgradeValues.TryGetValue("ArcaneContainment", out capacity);
            int available = System.Math.Max(2, System.Math.Min(4, (int)capacity));
            if (MyAPIGateway.Multiplayer.IsServer && initializationFrames == 0)
            {
                // Old saves did not store controller-derived ring capacity.
                // Adopt it once, after native socket connections have settled.
                if (restoreLegacyHardware)
                {
                    Motion.RingCount = available;
                    restoreLegacyHardware = false;
                }
                // Hardware stays latched through cooldown, dismantling and ejection.
                // Compare restored hardware too, after native connections settle.
                bool deployed = Motion.Core != CorePhase.Off || Motion.Vent != VentPhase.Idle;
                if (reactor.Enabled && (controllers < 2f || Motion.FuelTier + 1 > available
                    || (deployed && available != Motion.RingCount)))
                    reactor.Enabled = false;
                if (!deployed && controllers >= 2f) Motion.RingCount = available;
            }
            if (controllers == previousControllers && available == controllerRingCapacity) return;
            controllerRingCapacity = available;
            previousControllers = controllers;
            reactor.RefreshCustomInfo();
            MyLog.Default.WriteLineAndConsole("ArcanePower: reactor " + reactor.EntityId + " containment sockets=" + controllers);
        }

        private void UpdateAppearance()
        {
            if (MyAPIGateway.Utilities.IsDedicated) return;
            MyEntity entity = (MyEntity)Entity;
            MyEntitySubpart first;
            entity.Subparts.TryGetValue("Ring1", out first);
            bool venting = Motion.Vent != VentPhase.Idle;
            bool thermalWarning = Motion.ThermalWarning;
            bool incomplete = Motion.Status == ReactorStatus.Incomplete || venting || Motion.Critical || thermalWarning;
            bool precharging = Precharging;
            bool charging = precharging && PrechargeMW > .000001;
            pulseTick = (pulseTick + 1) % 120;
            // Subparts can exist before their render objects are ready on world
            // load. Retry once per second even when the entity/state is unchanged;
            // this also restores colours after a later render-object recreation.
            Color color = venting || Motion.Critical ? Color.Red
                : thermalWarning ? Color.Yellow
                : precharging ? Color.White
                : Motion.Status == ReactorStatus.Active ? FuelColors[Motion.FuelTier - 1]
                : Motion.Status == ReactorStatus.OutOfFuel ? Color.White : Color.Red;
            float intensity = EmissiveIntensity;
            if (incomplete || (precharging && !charging))
                intensity *= .5f + .5f * (float)System.Math.Cos(pulseTick * System.Math.PI / 60);
            else if (charging)
                intensity *= pulseTick % 60 < 30 ? 1f : 0f;
            if (incomplete || precharging || previousPrecharging != precharging || previousThermalWarning != thermalWarning || previousRing != first
                || previousFuelTier != Motion.FuelTier || previousStatus != Motion.Status || --appearanceRefresh <= 0)
            {
                appearanceRefresh = 60;
                previousRing = first;
                previousFuelTier = Motion.FuelTier;
                previousStatus = Motion.Status;
                previousPrecharging = precharging;
                previousThermalWarning = thermalWarning;
                entity.SetEmissiveParts("Emissive", color, intensity);
                entity.SetEmissivePartsForSubparts("Emissive", color, intensity);
            }
            MyEntitySubpart orb;
            float coreScale = PlasmaScale(Motion.CoreTick + Motion.CoreSubtick);
            Color fuelColor = FuelColors[Motion.FuelTier - 1];
            if (entity.Subparts.TryGetValue("Plasma", out orb))
                orb.SetEmissiveParts("ArcanePlasma", fuelColor, 0);
            UpdateCoreGlow(entity, fuelColor, coreScale);
        }

        private void UpdateCoreGlow(MyEntity entity, Color color, float emissivity)
        {
            MyEntitySubpart plasma;
            bool visible = entity.Subparts.TryGetValue("Plasma", out plasma)
                && !plasma.Closed && plasma.Render.Visible && Motion.Core != CorePhase.Off && !Motion.PayloadReleased;
            if (visible && coreGlow == null)
            {
                coreGlow = MyLights.AddLight();
                if (coreGlow == null) return;
                coreGlow.Start("Arcane Power containment glow");
                coreGlow.Range = 4.5f;
                coreGlow.Falloff = 2f;
                // This light approximates emission from the whole shell; its
                // opaque plasma/tile meshes must not shadow the emitter itself.
                coreGlow.CastShadows = false;
                coreGlow.GlareOn = false;
            }
            if (coreGlow == null) return;
            coreGlow.LightOn = visible && emissivity > .001f;
            coreGlow.Color = color;
            coreGlow.Intensity = 2.5f * emissivity;
            if (visible) coreGlow.Position = plasma.WorldMatrix.Translation;
            coreGlow.UpdateLight();
        }

        private void UpdateStatus()
        {
            if (!reactor.IsFunctional || reactor.SlimBlock.BuildLevelRatio < 1f || previousControllers < 2f || !CanOperate || Motion.TileStarved || Motion.PowerPaused)
            {
                Motion.Status = ReactorStatus.Incomplete;
                return;
            }
            bool hasFuel = HasUsableFuel();
            // Automatic shutdown disables the native reactor. Retain its fuel
            // starvation status until fuel arrives; its neutral white emissives
            // must not be confused with the yellow thermal alarm.
            if (!hasFuel && (reactor.Enabled || Motion.Status == ReactorStatus.OutOfFuel))
                Motion.Status = ReactorStatus.OutOfFuel;
            else Motion.Status = reactor.Enabled ? ReactorStatus.Active : ReactorStatus.ShutOff;
        }

        private void AppendInfo(IMyTerminalBlock block, StringBuilder info)
        {
            info.Append(ReadStatus(false).Text());
            info.Append("\nFull dashboard: LCD script 'Arcane Reactor'.\n");
        }

        public override void Close()
        {
            if (closing) return;
            closing = true;
            NeedsUpdate = MyEntityUpdateEnum.NONE;
            CloseSound();
            if (coreGlow != null)
            {
                MyLights.RemoveLight(coreGlow);
                coreGlow = null;
            }
            if (reactor == null) return;
            reactor.OnUpgradeValuesChanged -= CheckContainment;
            reactor.EnabledChanged -= ThermalEnabledChanged;
            ThermalSession.Remove(this);
            reactor.AppendingCustomInfo -= AppendInfo;
            if (fuelInventory != null)
            {
                fuelInventory.ContentsChanged -= FuelChanged;
                fuelInventory = null;
            }
            SaveMotion();
            VentSession.Remove(this);
        }
    }
}
