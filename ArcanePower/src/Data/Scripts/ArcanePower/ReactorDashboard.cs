using System;
using System.Collections.Generic;
using VRage.Game.GUI.TextPanel;
using VRageMath;

namespace ArcanePower
{
    // One layout feeds both native LCD sprites and the equipped tablet overlay.
    internal static class ReactorDashboard
    {
        internal static readonly string[] Pages = { "Overview", "Power", "Containment", "Supplies", "Vent" };
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
                Card(sprites, "OUTPUT / T" + report.Tier, report.Value("Output"), 22, 196, report.Load, "cyan");
                Card(sprites, "HEAT / CRITICAL AT 125%", report.Value("Heat"), 330, 196, report.Heat / 1.25, report.Heat >= 1 ? "red" : "yellow");
                Card(sprites, "EMERGENCY RESERVE", report.Value("Reserve"), 22, 285, report.Reserve, report.Reserve < .2 ? "red" : "green");
                Card(sprites, "SPARE CONTAINMENT TILES", report.Value("Spare tiles"), 330, 285, -1, "cyan");
                Rect(sprites, 22, 385, 596, 2, Tone("cyan"));
                Text(sprites, Pages[page].ToUpperInvariant(), 22, 397, .62f, Tone("cyan"));
                string[] labels = page == 0 ? new[] { "Net", "Field", "Fuel stock", "Vent" }
                    : page == 1 ? new[] { "Net", "Ramp", "Containment", "Fuel burn", "Fuel remaining" }
                    : page == 2 ? new[] { "Controllers", "Field", "Reserve energy", "Quartet wear", "Replacing", "Dismantle at" }
                    : page == 3 ? new[] { "Fuel stock", "Fuel remaining", "Tile demand", "Tile reserve", "Startup tiles", "Conveyors" }
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
