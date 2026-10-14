using System;
using Sandbox.Game.Entities;
using Sandbox.ModAPI;
using VRage.Game.Entity;
using VRageMath;

namespace ArcanePower
{
    public sealed partial class Reactor
    {
        private static readonly string[] LoopNames = {
            "Assembly", "Resonance", "Load", "Instability", "DeckMotion", "HatchMotion", "HatchMotion",
            "ResonancePitch1", "LoadPitch1", "ResonancePitch2", "LoadPitch2",
            "ResonancePitch3", "LoadPitch3", "ResonancePitch4", "LoadPitch4"
        };
        private MyEntity3DSoundEmitter[] soundLoops;
        private MySoundPair[] loopCues;
        private MyEntity3DSoundEmitter soundEvent;
        private readonly MechanismEvents mechanismEvents = new MechanismEvents();
        private MyEntity3DSoundEmitter dispenseSound, latchSound;
        private bool soundStateKnown;
        private CorePhase soundCore;
        private VentPhase soundVent;
        private int soundAge;
        private int soundTick;

        private void UpdateSound()
        {
            if (MyAPIGateway.Utilities.IsDedicated || !receivedState) return;
            var camera = MyAPIGateway.Session.Camera;
            bool nearby = camera != null && Vector3D.DistanceSquared(camera.Position, Entity.GetPosition()) < 160 * 160;
            // Remember transitions even outside earshot. Approaching or loading an
            // already running reactor restores loops without replaying ignition.
            if (nearby && soundStateKnown && initializationFrames == 0)
            {
                if (Motion.Vent == VentPhase.Ejecting && soundVent != VentPhase.Ejecting && Motion.VentHadPayload)
                    PlayReactorEvent("Vent");
                else if (Motion.Core == CorePhase.Stopping && soundCore != CorePhase.Stopping && soundAge > PlasmaStartTick)
                    PlayReactorEvent("Shutdown");
                else if (Motion.Core != CorePhase.Stopping && Motion.CoreTick > PlasmaStartTick && soundAge <= PlasmaStartTick
                    && soundCore == CorePhase.Starting && !Motion.PayloadReleased)
                    PlayReactorEvent("Ignition");
            }
            int mechanisms = mechanismEvents.Observe(Motion,
                nearby && soundStateKnown && initializationFrames == 0);
            if ((mechanisms & 1) != 0) PlayTileEvent(ref dispenseSound, "TileDispense", true);
            if ((mechanisms & 2) != 0) PlayTileEvent(ref latchSound, "TileLatch");
            if ((mechanisms & 4) != 0) PlayTileEvent(ref latchSound, "TileRetract");
            if ((mechanisms & 8) != 0) PlayTileEvent(ref dispenseSound, "TileLatch", true);
            soundStateKnown = true;
            soundCore = Motion.Core;
            soundVent = Motion.Vent;
            soundAge = Motion.CoreTick;
            if (!nearby) { CloseSound(); return; }
            if (soundEvent != null)
            {
                soundEvent.SetPosition(CoreWorldPosition());
                if (soundTick % 10 == 0) soundEvent.Update();
            }

            if (dispenseSound != null) dispenseSound.SetPosition(Entity.GetPosition() + Entity.WorldMatrix.Up * 1.98);
            if (latchSound != null) latchSound.SetPosition(CoreWorldPosition());
            if (soundTick % 10 == 0)
            {
                if (dispenseSound != null) dispenseSound.Update();
                if (latchSound != null) latchSound.Update();
            }
            bool present = Motion.Core != CorePhase.Off && !Motion.PayloadReleased;
            float age = Motion.CoreTick + Motion.CoreSubtick;
            float plasma = PlasmaScale(age);
            float load = Motion.Core == CorePhase.Cooling ? Math.Min(1, Motion.Heat) : Motion.Load;
            float strain = Motion.Critical ? 1 : MathHelper.Clamp((Motion.Heat - .8f) / .45f, 0, 1);
            if (Motion.TileStarved) strain = Math.Max(strain, .45f);
            float assembly = present && (Motion.Core == CorePhase.Starting || Motion.Core == CorePhase.Stopping)
                && !Motion.Paused ? (.12f + .28f * Span(age, 90, PlasmaStartTick)) * (1 - plasma) : 0;
            float field = FieldSoundGain(Motion.Core, Motion.Heat);
            float resonance = plasma * field * (.38f + .12f * load);
            float surge = plasma * field * load * .65f;
            // A stalled actuator is quiet; a hot residual field remains audible.
            float instability = present ? field * strain * .6f : 0;
            float deck = initializationFrames == 0 && MechanismEvents.DeckMoving(Motion) ? .5f : 0;
            float hatch = initializationFrames == 0 && MechanismEvents.HatchMoving(Motion) ? .5f : 0;
            if (soundLoops == null && assembly + resonance + surge + instability + deck + hatch < .001f) return;
            if (soundLoops == null)
            {
                soundLoops = new MyEntity3DSoundEmitter[LoopNames.Length];
                loopCues = new MySoundPair[LoopNames.Length];
                for (int i = 0; i < soundLoops.Length; i++)
                {
                    soundLoops[i] = new MyEntity3DSoundEmitter((MyEntity)Entity);
                    loopCues[i] = new MySoundPair("ArcaneReactor" + LoopNames[i]);
                }
            }
            soundTick++;
            MixLoop(0, assembly);
            MixHum(1, resonance);
            MixHum(2, surge);
            MixLoop(3, instability);
            MixLoop(4, deck);
            MixLoop(5, hatch);
            MixLoop(6, ventOutlet != null && !ventOutlet.Closed ? hatch : 0);
        }

        private static float FieldSoundGain(CorePhase core, float heat)
        {
            if (core == CorePhase.Off || core == CorePhase.Stopping) return 0;
            // Residual field response fades to silence at the dismantling threshold,
            // including when maintenance or loss of actuator power delays teardown.
            return core == CorePhase.Cooling
                ? MathHelper.Clamp((heat - CooldownHeat) / (1 - CooldownHeat), 0, 1) : 1;
        }

        private void MixHum(int baseIndex, float volume)
        {
            // SE mods cannot set a voice's pitch. Blend adjacent native pitched
            // cues instead; the synchronized one-second load response drives it.
            float step = MathHelper.Clamp(Motion.Load, 0, 1) * 4;
            for (int band = 0; band <= 4; band++)
            {
                float weight = (float)Math.Sqrt(Math.Max(0, 1 - Math.Abs(step - band)));
                int index = band == 0 ? baseIndex : 5 + 2 * band + baseIndex - 1;
                MixLoop(index, volume * weight);
            }
        }

        private void MixLoop(int index, float target)
        {
            target *= .7f; // Leave mix headroom when load and instability overlap.
            var emitter = soundLoops[index];
            // Short gain ramps prevent clicks when supply, load or state changes.
            float volume = (emitter.CustomVolume ?? 0) + (target - (emitter.CustomVolume ?? 0)) / 12;
            emitter.CustomVolume = volume;
            emitter.SetPosition(LoopSoundPosition(index));
            if (volume < .002f && target == 0)
            {
                emitter.StopSound(true);
                return;
            }
            // Mechanical loops respond immediately when motion starts. Stop
            // promptly on a stall so a frozen hatch does not keep its motor hum.
            bool mechanical = index >= 4 && index <= 6;
            if (mechanical && target == 0)
            { emitter.StopSound(true); emitter.CustomVolume = 0; return; }
            if (!mechanical && soundTick % 10 != 0) return;
            if (!emitter.IsPlaying) emitter.PlaySound(loopCues[index], stopPrevious: true, skipIntro: true);
            emitter.Update();
        }

        private Vector3D LoopSoundPosition(int index)
        {
            if (index == 4) return Entity.GetPosition() - Entity.WorldMatrix.Up * 1.26;
            if (index == 5) return Entity.GetPosition() + Entity.WorldMatrix.Up * 3.6;
            if (index == 6 && ventOutlet != null && !ventOutlet.Closed)
                return ventOutlet.WorldMatrix.Translation + ventOutlet.WorldMatrix.Up * 1.08;
            return CoreWorldPosition();
        }

        private void PlayTileEvent(ref MyEntity3DSoundEmitter emitter, string name, bool atDispenser = false)
        {
            if (emitter == null) emitter = new MyEntity3DSoundEmitter((MyEntity)Entity);
            emitter.SetPosition(atDispenser ? Entity.GetPosition() + Entity.WorldMatrix.Up * 1.98 : CoreWorldPosition());
            emitter.CustomVolume = .55f;
            emitter.PlaySound(new MySoundPair("ArcaneReactor" + name), stopPrevious: true);
        }

        private void PlayReactorEvent(string name)
        {
            if (soundEvent == null) soundEvent = new MyEntity3DSoundEmitter((MyEntity)Entity);
            soundEvent.SetPosition(CoreWorldPosition());
            soundEvent.PlaySound(new MySoundPair("ArcaneReactor" + name), stopPrevious: true);
        }

        private void CloseSound()
        {
            if (soundLoops != null)
                foreach (var emitter in soundLoops) emitter.StopSound(true);
            if (soundEvent != null) soundEvent.StopSound(true);
            if (dispenseSound != null) dispenseSound.StopSound(true);
            if (latchSound != null) latchSound.StopSound(true);
            dispenseSound = latchSound = null;
            soundLoops = null;
            loopCues = null;
            soundEvent = null;
        }
    }
}
