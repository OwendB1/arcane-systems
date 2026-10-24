using System;
using System.Collections.Generic;
using VRage.Game.GUI.TextPanel;
using VRageMath;

namespace ArcanePower
{
    // Native block LCDs and the handheld screen share telemetry and sprite helpers.
    internal static class ReactorDashboard
    {
        internal static readonly string[] Pages = { "Overview", "Power", "Containment", "Supplies", "Vent" };
        internal const float TabletWidth = 640;
        internal const float TabletHeight = TabletWidth * .174f / .270f;
        internal static Color Tone(string tone)
        {
            switch (tone)
            {
                case "red": return new Color(238, 82, 82);
                case "yellow": return new Color(255, 178, 66);
                case "green": return new Color(78, 210, 118);
                case "cyan": return new Color(70, 190, 220);
                case "muted": return new Color(160, 170, 180);
                default: return new Color(235, 240, 245);
            }
        }
        internal static List<MySprite> Draw(StatusReport report, int page, string message, string footer)
        {
            var sprites = new List<MySprite>();
            Rect(sprites, 0, 0, 640, 640, new Color(8, 10, 13));
            Rect(sprites, 0, 0, 640, 78, new Color(18, 24, 31));
            Text(sprites, "ARCANE / POWER", 22, 14, .67f, Tone("cyan"));
            Text(sprites, report == null ? "REACTOR TERMINAL" : Clip(report.Name, 35), 22, 43, .74f, Tone("white"));
            if (report == null)
            {
                Text(sprites, "DISCONNECTED", 22, 112, .9f, Tone("yellow"));
                Wrapped(sprites, message, 22, 163, .65f, Tone("muted"), 45);
                Text(sprites, "READ-ONLY TELEMETRY", 22, 520, .6f, Tone("cyan"));
            }
            else
            {
                Text(sprites, Clip(report.State, 46), 22, 91, .64f, Tone(report.Tone));
                float y = 122;
                foreach (var row in report.Rows)
                    if (row.Section == null)
                    { Wrapped(sprites, row.Value, 22, y, .48f, Tone(row.Tone), 63); y += 36; }
                // Keep alert space reserved; cards and page body never jump around.
                Card(sprites, "OUTPUT / " + report.Fuel.ToUpperInvariant(), report.Value("Output"), 22, 196, report.Load, "cyan");
                Card(sprites, "HEAT / CRITICAL AT 125%", report.Value("Heat"), 330, 196, report.Heat / 1.25, report.Heat > 1 ? "red" : "yellow");
                Card(sprites, report.Precharging ? "STARTUP CHARGE" : "EMERGENCY RESERVE",
                    report.Value(report.Precharging ? "Startup charge" : "Reserve"), 22, 285, report.Reserve,
                    report.Precharging ? report.Tone : report.Reserve < .2 ? "red" : "green");
                Card(sprites, "SPARE CONTAINMENT TILES", report.Value("Spare tiles"), 330, 285, -1, "cyan");
                Rect(sprites, 22, 385, 596, 2, Tone("cyan"));
                Text(sprites, Pages[page].ToUpperInvariant(), 22, 397, .62f, Tone("cyan"));
                string[] labels = report.Precharging && (page == 0 || page == 1)
                    ? new[] { "Containment", "Charge rate", "Charge ETA", "Reserve energy", "Net" }
                    : page == 0 ? new[] { "Net", "Field", "Fuel stock", "Vent" }
                    : page == 1 && report.Brayton ? new[] { "Circuits available", "Conversion efficiency", "Cooling capacity", "Cooling required", "Returned waste" }
                    : page == 1 ? new[] { "Net", "Ramp", "Containment", "Fuel burn", "Fuel remaining" }
                    : page == 2 ? new[] { "Controllers", "Field", "Reserve energy", "Tile grade", "Replacing", "Dismantle at" }
                    : page == 3 ? new[] { "Fuel stock", "Fuel remaining", "Tile demand", "Tile reserve", "Tile stock", "Conveyors" }
                    : new[] { "Vent", "Route", "Doors" };
                y = 432;
                foreach (var label in labels)
                {
                    foreach (var row in report.Rows)
                    {
                        if (row.Label != label) continue;
                        Rect(sprites, 22, y - 2, 596, 25, ((int)y % 2 == 0) ? new Color(16,20,26) : new Color(22,27,34));
                        Text(sprites, label, 28, y, .46f, Tone("muted"));
                        Text(sprites, Clip(row.Value, 44), 202, y, .46f, Tone(row.Tone));
                        y += 27;
                        break;
                    }
                }
                if (page == 4) Wrapped(sprites, "Venting ejects containment. Restart manually. Critical cores still detonate after ejection.", 28, y + 10, .48f, Tone("yellow"), 62);
            }
            Rect(sprites, 0, 610, 640, 30, new Color(18,24,31));
            Text(sprites, Clip(footer, 68), 22, 617, .43f, Tone("muted"));
            return sprites;
        }
        internal static List<MySprite> DrawTablet(StatusReport report, int page, string message)
        {
            var sprites = new List<MySprite>();
            Rect(sprites, 0, 0, TabletWidth, TabletHeight, new Color(8, 10, 13));
            Rect(sprites, 0, 0, TabletWidth, 78, new Color(18, 24, 31));
            Text(sprites, "ARCANE / " + Pages[page].ToUpperInvariant(), 18, 12, .7f, Tone("cyan"));
            Text(sprites, report == null ? "REACTOR TABLET" : Clip(report.Name, 38), 18, 42, .74f, Tone("white"));
            if (report == null)
            {
                Text(sprites, "DISCONNECTED", 18, 96, .8f, Tone("yellow"));
                Wrapped(sprites, message, 18, 144, .65f, Tone("muted"), 46);
            }
            else
            {
                Text(sprites, Clip(report.State, 48), 18, 88, .62f, Tone(report.Tone));
                if (report.Precharging)
                {
                    Rect(sprites, 18, 111, 604, 3, new Color(48, 55, 64));
                    Rect(sprites, 18, 111, (float)(604 * MathHelper.Clamp(report.Reserve, 0, 1)), 3, Tone(report.Tone));
                }
                float y = 118;
                foreach (var row in report.Rows)
                    if (row.Section == null)
                    { Text(sprites, Clip(row.Value, 72), 18, y, .42f, Tone(row.Tone)); y += 22; }
                string[] labels = report.Precharging && (page == 0 || page == 1)
                    ? new[] { "Startup charge", "Reserve energy", "Containment", "Charge rate", "Charge ETA", "Net", "Vent" }
                    : page == 0 ? new[] { "Output", "Heat", "Reserve", "Fuel stock", "Spare tiles", "Vent" }
                    : page == 1 && report.Brayton ? new[] { "Output", "Circuits available", "Conversion efficiency", "Cooling capacity", "Cooling required", "Returned waste", "Startup / cooldown draw" }
                    : page == 1 ? new[] { "Output", "Net", "Ramp", "Containment", "Fuel efficiency", "Fuel burn", "Fuel remaining" }
                    : page == 2 ? new[] { "Security mode", "Integrity", "Controllers", "Field", "Reserve energy", "Tile grade", "Quartet wear", "Replacing", "Dismantle at" }
                    : page == 3 ? new[] { "Fuel efficiency", "Fuel stock", "Fuel burn", "Fuel remaining", "Spare tiles", "Tile demand", "Tile reserve", "Tile stock", "Startup tiles", "Conveyors" }
                    : new[] { "Vent", "Route", "Doors", "Security mode", "Integrity" };
                var rows = new List<StatusRow>();
                foreach (string label in labels)
                    foreach (var row in report.Rows)
                        if (row.Label == label) { rows.Add(row); break; }
                float spacing = Math.Min(34, (TabletHeight - 44 - y) / Math.Max(1, rows.Count));
                float rowFont = Math.Min(.57f, (spacing - 3) / 37);
                for (int i = 0; i < rows.Count; i++)
                {
                    var row = rows[i];
                    Rect(sprites, 12, y - 1, 616, spacing - 2, i % 2 == 0 ? new Color(16, 20, 26) : new Color(22, 27, 34));
                    Text(sprites, row.Label, 18, y, Math.Min(.5f, rowFont), Tone("muted"));
                    float font = Math.Min(rowFont, 442f / (Math.Max(1, row.Value.Length) * 20));
                    Text(sprites, row.Value, 180, y, font, Tone(row.Tone));
                    y += spacing;
                }
            }
            Rect(sprites, 0, TabletHeight - 30, TabletWidth, 30, new Color(18, 24, 31));
            Text(sprites, "LMB: reactor   RMB: page   / READ ONLY", 18, TabletHeight - 23, .54f, Tone("muted"));
            return sprites;
        }

        private static void Card(List<MySprite> s, string label, string value, float x, float y, double progress, string tone)
        {
            Rect(s,x,y,288,77,new Color(24,30,38)); Rect(s,x,y,3,77,Tone(tone));
            Text(s,label,x+12,y+10,Math.Min(.40f,264f/(Math.Max(1,label.Length)*20)),Tone("muted"));
            Text(s,value,x+12,y+31,Math.Min(.57f,264f/(Math.Max(1,value.Length)*20)),Tone("white"));
            if (progress >= 0)
            { Rect(s,x+12,y+65,264,4,new Color(48,55,64)); Rect(s,x+12,y+65,(float)(264*MathHelper.Clamp(progress,0,1)),4,Tone(tone)); }
        }
        private static string Clip(string value, int limit) { return value.Length <= limit ? value : value.Substring(0, limit - 3) + "..."; }
        private static void Wrapped(List<MySprite> s,string value,float x,float y,float scale,Color color,int width)
        {
            if (value == null) return;
            while (value.Length > width)
            {
                int split=value.LastIndexOf(' ',width); if (split<1) split=width;
                Text(s,value.Substring(0,split),x,y,scale,color); value=value.Substring(split).TrimStart(); y+=22;
            }
            Text(s,value,x,y,scale,color);
        }
        private static void Text(List<MySprite> s,string text,float x,float y,float scale,Color color)
        { var sprite=MySprite.CreateText(text,"Monospace",color,scale,TextAlignment.LEFT); sprite.Position=new Vector2(x,y); s.Add(sprite); }
        private static void Rect(List<MySprite> s,float x,float y,float width,float height,Color color)
        { if(width>0) s.Add(new MySprite(SpriteType.TEXTURE,"SquareSimple",new Vector2(x+width/2,y+height/2),new Vector2(width,height),color)); }
    }
}
