package org.squinchmods.investigate.rtf.surfacerescue;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;

import net.minecraft.core.BlockPos;
import net.minecraft.core.Holder;
import net.minecraft.core.registries.Registries;
import net.minecraft.resources.ResourceKey;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.util.RandomSource;
import net.minecraft.world.level.levelgen.placement.PlacedFeature;
import org.squinchmods.investigate.ProbeExecution;
import org.squinchmods.investigate.ProbePack;
import org.squinchmods.investigate.ProbePhase;
import org.squinchmods.investigate.ProbeRegistry;
import org.squinchmods.investigate.ProbeRequest;
import org.squinchmods.investigate.ProbeResult;
import org.squinchmods.investigate.TerminalState;

public final class SurfaceRescueCrashProbePack implements ProbePack {
    @Override
    public void register() {
        ProbeRegistry.register("squinch:rtf-surface-rescue-crash", "1", SurfaceRescueCrashProbe::new);
    }

    private static final class SurfaceRescueCrashProbe implements ProbeExecution {
        private final ResourceLocation featureId;
        private final BlockPos pos;
        private final int attempts;

        private SurfaceRescueCrashProbe(ProbeRequest request) {
            JsonObject config = request.config();
            this.featureId = ResourceLocation.parse(config.get("feature_id").getAsString());
            JsonArray posArray = config.getAsJsonArray("pos");
            this.pos = new BlockPos(
                posArray.get(0).getAsInt(),
                posArray.get(1).getAsInt(),
                posArray.get(2).getAsInt()
            );
            this.attempts = config.has("attempts") ? config.get("attempts").getAsInt() : 50;
            if (this.attempts <= 0) {
                throw new IllegalArgumentException("attempts must be positive");
            }
        }

        @Override
        public ProbeResult tick(MinecraftServer server) throws Exception {
            ServerLevel level = server.overworld();
            Holder<PlacedFeature> holder = level.registryAccess()
                .registryOrThrow(Registries.PLACED_FEATURE)
                .getHolderOrThrow(ResourceKey.create(Registries.PLACED_FEATURE, this.featureId));
            PlacedFeature feature = holder.value();
            RandomSource random = RandomSource.create(level.getSeed() ^ this.pos.asLong());

            JsonArray modifierClasses = new JsonArray();
            for (var modifier : feature.placement()) {
                modifierClasses.add(modifier.getClass().getName());
            }

            JsonObject diagnostics = diagnose(level, feature, this.featureId);

            int placedCount = 0;
            for (int i = 0; i < this.attempts; i++) {
                if (feature.placeWithBiomeCheck(level, level.getChunkSource().getGenerator(), random, this.pos)) {
                    placedCount++;
                }
            }

            JsonObject data = new JsonObject();
            data.addProperty("feature_id", this.featureId.toString());
            data.addProperty("pos_x", this.pos.getX());
            data.addProperty("pos_y", this.pos.getY());
            data.addProperty("pos_z", this.pos.getZ());
            data.addProperty("attempts", this.attempts);
            data.addProperty("placed_count", placedCount);
            data.add("placement_modifier_classes", modifierClasses);
            data.add("diagnostics", diagnostics);
            return ProbeResult.complete(TerminalState.PASS, ProbePhase.PLACEMENT, data, this.attempts);
        }

        private static JsonObject diagnose(
            ServerLevel level,
            PlacedFeature feature,
            ResourceLocation featureId
        ) throws ReflectiveOperationException {
            JsonObject diagnostics = new JsonObject();
            diagnostics.addProperty("min_gen_y", level.getMinBuildHeight());
            diagnostics.addProperty("height", level.getHeight());

            Class<?> dynamicHeightRangePlacementClass = Class.forName(
                "raccoonman.reterraforged.world.worldgen.feature.placement.DynamicHeightRangePlacement"
            );
            diagnostics.addProperty("reference_min_y", (Integer) dynamicHeightRangePlacementClass
                .getField("REFERENCE_MIN_Y").get(null));
            diagnostics.addProperty("reference_max_y", (Integer) dynamicHeightRangePlacementClass
                .getField("REFERENCE_MAX_Y").get(null));
            diagnostics.addProperty("is_rtf_generator", Class.forName(
                "raccoonman.reterraforged.world.worldgen.runtime.TerraForgedChunkGenerator"
            ).isInstance(level.getChunkSource().getGenerator()));

            Class<?> classifierClass = Class.forName(
                "raccoonman.reterraforged.world.worldgen.feature.placement.SurfacePlacementClassifier"
            );
            java.lang.reflect.Method classify = classifierClass.getDeclaredMethod(
                "classify",
                PlacedFeature.class,
                java.util.Optional.class,
                net.minecraft.core.HolderLookup.Provider.class
            );
            classify.setAccessible(true);
            Object classification = classify.invoke(
                null,
                feature,
                java.util.Optional.of(featureId),
                level.registryAccess()
            );
            java.lang.reflect.Method eligible = classification.getClass().getDeclaredMethod("eligible");
            eligible.setAccessible(true);
            diagnostics.addProperty("classification_eligible", (Boolean) eligible.invoke(classification));
            return diagnostics;
        }
    }
}
