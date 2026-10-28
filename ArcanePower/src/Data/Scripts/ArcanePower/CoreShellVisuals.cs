using System;
using System.Collections.Generic;
using Sandbox.Common.ObjectBuilders;
using Sandbox.Definitions;
using VRage.Game;
using VRage.Game.Entity;
using VRage.ModAPI;
using VRage.ObjectBuilders;
using VRageMath;

namespace ArcanePower
{
    // Reuse the authored shell meshes as rigid children of the plasma carrier.
    // Only the carrier has physics; shell parts cannot scatter or be collected.
    internal sealed class CoreShellVisuals
    {
        private readonly MyEntity parent;
        private readonly List<CoreShellPart> parts;
        private readonly List<MyEntitySubpart> children = new List<MyEntitySubpart>();
        private int retryFrames;

        internal CoreShellVisuals(MyEntity entity, List<CoreShellPart> shell)
        { parent = entity; parts = shell; }

        internal void Update()
        {
            if (retryFrames > 0) { retryFrames--; return; }
            try
            {
                for (int i = children.Count; i < parts.Count; i++)
                {
                    var definition = MyDefinitionManager.Static.GetPhysicalItemDefinition(
                        new MyDefinitionId(typeof(MyObjectBuilder_Component), parts[i].Subtype));
                    var child = new MyEntitySubpart();
                    children.Add(child);
                    child.Init(null, definition.Model, parent, null);
                    child.Render.NeedsDrawFromParent = false;
                    child.Render.PersistentFlags = parent.Render.PersistentFlags & ~MyPersistentEntityFlags2.InScene;
                    parent.Subparts["ArcaneCoreShell" + i] = child;
                    if (parent.InScene) child.OnAddedToScene(parent);
                    child.Flags &= ~EntityFlags.IsGamePrunningStructureObject;
                    Matrix pose = parts[i].Pose;
                    child.PositionComp.SetLocalMatrix(ref pose);
                }
            }
            catch (Exception error)
            {
                Close();
                retryFrames = 120;
                VRage.Utils.MyLog.Default.WriteLine("ArcanePower: critical shell visual unavailable: " + error.Message);
            }
        }

        internal void Close()
        {
            for (int i = 0; i < children.Count; i++)
            {
                var child = children[i];
                MyEntitySubpart owned;
                string key = "ArcaneCoreShell" + i;
                if (parent.Subparts != null && parent.Subparts.TryGetValue(key, out owned) && owned == child)
                    parent.Subparts.Remove(key);
                if (!child.Closed && !child.MarkedForClose)
                { parent.Hierarchy.RemoveChild(child); child.Close(); }
            }
            children.Clear();
        }
    }
}
