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
    [MyEntityComponentDescriptor(typeof(MyObjectBuilder_Reactor), false, "ArcanePower_ReactorPrototype")]
    public sealed partial class Reactor : MyGameLogicComponent
    {
        private IMyReactor reactor;
        // Native upgrade modules refresh connections on their 100-frame update.
        // Keep the saved pose parked until that pass, then prime power for two ticks.
        private int initializationFrames = 120;
        private bool motionInitialized;
        private float previousControllers = -1;
        private int rings = 2;
        private int previousRings;
        private MyEntitySubpart previousRing;
        private int appearanceRefresh;
        private ReactorStatus previousStatus;
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
            reactor.OnUpgradeValuesChanged += CheckContainment;
            reactor.AppendingCustomInfo += AppendInfo;
            NeedsUpdate = MyEntityUpdateEnum.EACH_FRAME;
            InitializeMotion();
            CheckContainment();
            InitializeFuel();
        }

        public override void UpdateBeforeSimulation()
        {
            if (initializationFrames > 0)
            {
                if (--initializationFrames > 0)
                {
                    CheckContainment();
                    if (initializationFrames <= 2)
                    {
                        UpdateFuel();
                        UpdatePower();
                    }
                    if (!MyAPIGateway.Utilities.IsDedicated)
                    {
                        DrawMotion();
                        DrawVentOutlet();
                    }
                    UpdateAppearance();
                    return;
                }
            }
            // Native module connection events update the value. The enabled guard also
            // catches manual/toolbar attempts to start without the two controllers.
            CheckContainment();
            UpdateFuel();
            UpdatePower();
            UpdateTiles();
            UpdateMotion();
            UpdateAppearance();
        }

        private void CheckContainment()
        {
            float controllers, capacity;
            reactor.UpgradeValues.TryGetValue("ArcaneControllerCount", out controllers);
            reactor.UpgradeValues.TryGetValue("ArcaneContainment", out capacity);
            int available = System.Math.Max(2, System.Math.Min(4, (int)capacity));
            if (MyAPIGateway.Multiplayer.IsServer && initializationFrames == 0 && controllers < 2f && reactor.Enabled)
                reactor.Enabled = false;
            // Changing installed containment hardware requires a fresh deployment.
            if (MyAPIGateway.Multiplayer.IsServer && initializationFrames == 0 && previousControllers >= 0 && (available != rings || Motion.Profile > available) && reactor.Enabled)
                reactor.Enabled = false;
            if (controllers == previousControllers && available == rings) return;
            rings = available;
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
            bool incomplete = Motion.Status == ReactorStatus.Incomplete || venting || Motion.Critical;
            pulseTick = (pulseTick + 1) % 120;
            // Subparts can exist before their render objects are ready on world
            // load. Retry once per second even when the entity/state is unchanged;
            // this also restores colours after a later render-object recreation.
            Color color = venting || Motion.Critical ? Color.Red : Motion.Status == ReactorStatus.Active ? FuelColors[Motion.Profile - 2]
                : Motion.Status == ReactorStatus.OutOfFuel ? Color.Yellow : Color.Red;
            float intensity = EmissiveIntensity * (incomplete ? .5f + .5f * (float)System.Math.Cos(pulseTick * System.Math.PI / 60) : 1f);
            if (incomplete || previousRing != first || previousRings != Motion.Profile || previousStatus != Motion.Status || --appearanceRefresh <= 0)
            {
                appearanceRefresh = 60;
                previousRing = first;
                previousRings = Motion.Profile;
                previousStatus = Motion.Status;
                entity.SetEmissiveParts("Emissive", color, intensity);
                entity.SetEmissivePartsForSubparts("Emissive", color, intensity);
            }
            if (Motion.Core == CorePhase.Stopping)
            {
                MyEntitySubpart plasma;
                if (entity.Subparts.TryGetValue("Plasma", out plasma))
                    plasma.SetEmissiveParts("Emissive", color, intensity * (1 - Span(Motion.StopTick, 0, 60)));
            }
            MyEntitySubpart orb;
            float coreFade = Motion.Core == CorePhase.Stopping ? 1 - Span(Motion.StopTick, 0, 60) : 1;
            Color fuelColor = FuelColors[Motion.Profile - 2];
            if (entity.Subparts.TryGetValue("Plasma", out orb))
                orb.SetEmissiveParts("ArcanePlasma", fuelColor, 18 * coreFade * (.9f + .1f * (float)System.Math.Sin(pulseTick * .13)));
            UpdateCoreGlow(entity, fuelColor, EmissiveIntensity);
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
            float fade = Motion.Core == CorePhase.Stopping ? 1 - Span(Motion.StopTick, 0, 60) : 1;

            coreGlow.LightOn = visible && fade > 0 && emissivity > .01f;
            coreGlow.Color = color;
            coreGlow.Intensity = 2.5f * emissivity / EmissiveIntensity * fade;
            if (visible) coreGlow.Position = plasma.WorldMatrix.Translation;
            coreGlow.UpdateLight();
        }

        private void UpdateStatus()
        {
            if (!reactor.IsFunctional || reactor.SlimBlock.BuildLevelRatio < 1f || previousControllers < 2f || Motion.TileStarved || Motion.PowerPaused)
            {
                Motion.Status = ReactorStatus.Incomplete;
                return;
            }
            bool hasFuel = HasUsableFuel();
            // Automatic shutdown disables the native reactor. Retain its fuel
            // starvation indication until fuel arrives instead of turning red.
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
            if (coreGlow != null)
            {
                MyLights.RemoveLight(coreGlow);
                coreGlow = null;
            }
            if (reactor == null) return;
            reactor.OnUpgradeValuesChanged -= CheckContainment;
            reactor.AppendingCustomInfo -= AppendInfo;
            ((VRage.Game.Entity.MyInventoryBase)reactor.GetInventory()).ContentsChanged -= FuelChanged;
            SaveMotion();
            VentSession.Remove(this);
        }
    }
}
