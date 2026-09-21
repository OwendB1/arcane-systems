"""Exercise the actual appearance method against delayed/recreated render objects.

Uses recording stand-ins, not a running game. Requires Mono's mcs and mono.
"""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
source = (root / 'src/Data/Scripts/ArcanePower/Reactor.cs').read_text()
fields = source[source.index('        private IMyReactor reactor;'):source.index('        public override void Init')]
method = source[source.index('        private void UpdateAppearance()'):source.index('        private void AppendInfo')]
stub = r'''
using System;
using System.Collections.Generic;
struct Color {
    public int R; public Color(int r,int g,int b){R=r;}
    public static Color Black = new Color(0,0,0);
}
class IMyReactor { public bool IsWorking; }
static class MyAPIGateway { public static class Utilities { public static bool IsDedicated; } }
class Render { public bool Visible; }
class MyEntity {
    public Dictionary<string,MyEntitySubpart> Subparts = new Dictionary<string,MyEntitySubpart>();
    public bool Ready; public int Applied; public float Intensity; public Color Color;
    public Render Render = new Render();
    public void SetEmissiveParts(string name,Color color,float intensity) {
        if(Ready){Applied++;Color=color;Intensity=intensity;}
    }
    public void SetEmissivePartsForSubparts(string name,Color color,float intensity) {
        foreach(var p in Subparts.Values)p.SetEmissiveParts(name,color,intensity);
    }
}
class MyEntitySubpart : MyEntity {}
class AppearanceCheck {
    public MyEntity Entity = new MyEntity();
'''
checks = r'''
    static void Require(bool condition,string message){if(!condition)throw new Exception(message);}
    static void Main(){
        var t=new AppearanceCheck(); t.reactor=new IMyReactor{IsWorking=true};
        for(int i=1;i<=4;i++)t.Entity.Subparts["Ring"+i]=new MyEntitySubpart();
        var ring=t.Entity.Subparts["Ring1"];
        t.UpdateAppearance(); // Objects exist; renderer is not ready yet.
        Require(ring.Applied==0,"fixture must drop initial render update");
        t.Entity.Ready=true; foreach(var p in t.Entity.Subparts.Values)p.Ready=true;
        for(int i=0;i<60;i++)t.UpdateAppearance();
        Require(ring.Applied==1 && ring.Intensity==1 && ring.Color.R==40,"initial load must recover without toggle");
        var late=new MyEntitySubpart{Ready=true};t.Entity.Subparts["Ring4"]=late;
        for(int i=0;i<60;i++)t.UpdateAppearance();
        Require(late.Applied==1,"later child replacement must recover even with same Ring1");
        t.rings=4;t.UpdateAppearance();
        Require(late.Color.R==180 && late.Render.Visible,"profile changes must apply immediately");
        t.reactor.IsWorking=false;t.UpdateAppearance();
        Require(ring.Intensity==0,"shutdown must darken immediately");
        int before=ring.Applied;MyAPIGateway.Utilities.IsDedicated=true;
        for(int i=0;i<65;i++)t.UpdateAppearance();
        Require(ring.Applied==before,"dedicated server must skip rendering");
        Console.WriteLine("PASS: delayed first render, later child replacement, immediate profile/off changes, dedicated skip");
    }
}
'''
with tempfile.TemporaryDirectory(prefix='arcane-appearance-') as folder:
    path = Path(folder) / 'check.cs'
    path.write_text(stub + fields + method + checks)
    exe = path.with_suffix('.exe')
    subprocess.run(['mcs', '-warn:0', '-out:' + str(exe), str(path)], check=True)
    subprocess.run(['mono', str(exe)], check=True)
