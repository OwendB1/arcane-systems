using System.Collections.Generic;
using Sandbox.Game.Components;
using Sandbox.Game.Entities;
using VRage.Collections;
using VRage.Game.GUI.TextPanel;
using VRageMath;

namespace ArcanePower
{
    // Use SE's LCD texture renderer on the hand tool's existing screen material.
    // The tool keeps its native renderer, including first-person movement/lighting.
    internal sealed class TabletScreen
    {
        private const string Material = "ArcaneTabletScreen";
        private static readonly Vector2I Resolution = new Vector2I(1024, 1024);
        private static readonly Vector2 Aspect = new Vector2(.270f / .174f, 1);
        private MyHandToolBase owner;
        private MyRenderComponentScreenAreas renderer;
        private uint[] renderIds;

        internal bool Draw(MyHandToolBase tool, List<MySprite> sprites)
        {
            uint[] ids = tool.Render.RenderObjectIDs;
            if (tool != owner || !SameIds(ids)) Release();
            if (renderer == null)
            {
                bool ready = false;
                foreach (uint id in ids) if (id != uint.MaxValue) ready = true;
                if (!ready) return false;
                owner = tool;
                renderIds = (uint[])ids.Clone();
                renderer = new MyRenderComponentScreenAreas(tool) { IsUpdateModelPropertiesEnabled = false };
                // Bind an offscreen helper without replacing the hand-tool renderer.
                // Its texture methods use these existing render IDs; no grid is spawned.
                renderer.SetContainer(tool.Components);
                renderer.AddScreenArea(ids, Material);
                renderer.CreateTexture(0, Resolution);
            }

            Vector2 surface = (Vector2)Resolution * Aspect;
            float scale = surface.X / ReactorDashboard.TabletWidth;
            Vector2 shift = (Vector2)Resolution * (Aspect - Vector2.One) / 2;
            var scaled = new List<MySprite>(sprites.Count);
            foreach (var original in sprites)
            {
                var sprite = original;
                if (sprite.Position.HasValue) sprite.Position = sprite.Position.Value * scale - shift;
                if (sprite.Size.HasValue) sprite.Size = sprite.Size.Value * scale;
                // Font units and positions must use the same fitted canvas scale.
                // A second 10% factor made glyphs disappear in the screen's mipmaps.
                if (sprite.Type == SpriteType.TEXT) sprite.RotationOrScale *= scale;
                scaled.Add(sprite);
            }
            renderer.RenderSpritesToTexture(0, new ListReader<MySprite>(scaled), Resolution, Aspect, Color.Black, 255);
            renderer.ChangeTexture(0, renderer.GenerateOffscreenTextureName(tool.EntityId, 0));
            // Light the panel itself without tinting the telemetry colours.
            tool.SetEmissiveParts(Material, Color.White, 2f);
            return true;
        }

        private bool SameIds(uint[] ids)
        {
            if (renderIds == null || renderIds.Length != ids.Length) return false;
            for (int i = 0; i < ids.Length; i++) if (ids[i] != renderIds[i]) return false;
            return true;
        }

        internal void Release()
        {
            if (renderer == null) return;
            if (!owner.Closed && SameIds(owner.Render.RenderObjectIDs))
            {
                owner.SetEmissiveParts(Material, Color.White, 0f);
                renderer.ChangeTexture(0, null);
            }
            renderer.ReleaseTexture(0, false);
            renderer.SetContainer(null);
            renderer = null;
            owner = null;
            renderIds = null;
        }
    }
}
