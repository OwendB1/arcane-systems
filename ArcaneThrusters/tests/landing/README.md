# Repeat the offline landing comparison

Use a scratch offline SE1 survival save with XML sector data, a local player identity, and a running se-remote client. The generator reads the seed, loads Earthlike from the installed Home System content and creates a new save for each run. It embeds the current example script directly in the lander's programmable block.

From the repository root, set the paths for the local installation and create both trials. The local mod folder names default to `ArcanePower-Prototype` and `ArcaneThrusters-RecoveryReview`. Pass `--power-mod` and `--thrusters-mod` to use different names.

```sh
seed='/path/to/offline-xml-save'
home_system='/path/to/SpaceEngineers/Content/CustomWorlds/Home System'
mods='/path/to/SpaceEngineers/Mods'
remote_dir='/path/to/se-remote/skills/se-remote'
se-remote() { (cd "$remote_dir" && uv run se_remote.py "$@"); }
trials=$(mktemp -d)
mkdir -p "$mods/ArcaneLanderTest/Data/Scripts/Probe"
cp ArcaneThrusters/tests/landing/LandingProbe.cs "$mods/ArcaneLanderTest/Data/Scripts/Probe/"
for mode in off on; do
    python3 ArcaneThrusters/tests/landing/prepare.py "$seed" "$home_system" "$trials/$mode" --assist "$mode"
done
se-remote load "$trials/off" --online-mode OFFLINE
```

If SE shows its XML conversion notice, dismiss it with `se-remote control-click OK --screen 0`. Wait for `LANDING ... TOUCHDOWN Test assist off` in the game log, then load `"$trials/on"` the same way. The probe prints `FAIL` if the fixture loses a block, the trim checks fail, initial conditions differ from the specified release, or touchdown cannot be confirmed.

Compare the two touchdown lines. Each reports the last airborne tilt, horizontal center-of-mass displacement, descent speed, skid clearance, and the following collision impulse expressed as the change in vertical speed. Both flights use the same speed governor and pad. The PB is the only source of steering during descent.
