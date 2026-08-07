package org.squinchmods.investigate.rtf;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeMap;
import java.util.TreeSet;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.mojang.datafixers.util.Pair;

import net.minecraft.core.Holder;
import net.minecraft.core.QuartPos;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.biome.Biome;
import net.minecraft.world.level.biome.BiomeSource;
import net.minecraft.world.level.biome.Climate;
import net.minecraft.world.level.biome.MultiNoiseBiomeSource;
import org.squinchmods.investigate.FinishedChunkSelection;
import org.squinchmods.investigate.MinecraftProbeHelpers;
import org.squinchmods.investigate.ProbeExecution;
import org.squinchmods.investigate.ProbePack;
import org.squinchmods.investigate.ProbeRegistry;
import org.squinchmods.investigate.ProbeRequest;
import org.squinchmods.investigate.ProbeResult;
import org.squinchmods.investigate.rtf.mixin.AccessorMultiNoiseBiomeSource;

public final class RtfCompositionAuditProbePack implements ProbePack {
    @Override
    public void register() {
        ProbeRegistry.register("squinch:rtf-composition-audit", "1", CompositionAudit::new);
    }

    private static final class CompositionAudit implements ProbeExecution {
        private final FinishedChunkSelection selection;
        private final int horizontalQuartStep;
        private final int verticalQuartStep;
        private final int surfaceThresholdY;

        private CompositionAudit(ProbeRequest request) {
            JsonObject config = request.config();
            this.selection = new FinishedChunkSelection(config, "rtf-composition-audit");
            this.horizontalQuartStep = config.has("horizontal_quart_step")
                ? config.get("horizontal_quart_step").getAsInt() : 1;
            this.verticalQuartStep = config.has("vertical_quart_step")
                ? config.get("vertical_quart_step").getAsInt() : 2;
            this.surfaceThresholdY = config.has("surface_threshold_y")
                ? config.get("surface_threshold_y").getAsInt() : 62;
        }

        @Override
        public ProbeResult tick(net.minecraft.server.MinecraftServer server) {
            ServerLevel level = server.overworld();
            FinishedChunkSelection.Snapshot snapshot = this.selection.poll(level);
            if (snapshot == null) return null;

            BiomeSource biomeSource = level.getChunkSource().getGenerator().getBiomeSource();
            if (!(biomeSource instanceof MultiNoiseBiomeSource mnbs)) {
                JsonObject data = new JsonObject();
                data.addProperty("error", "BiomeSource is not MultiNoiseBiomeSource");
                return this.selection.result(snapshot, data);
            }

            List<Pair<Climate.ParameterPoint, Holder<Biome>>> rawEntries =
                ((AccessorMultiNoiseBiomeSource) (Object) mnbs).invokeParameters().values();

            TreeAnalysis tree = analyzeTree(rawEntries);
            ChunkSurvey survey = surveyFinishedChunks(snapshot, level, tree.registeredBiomes);

            return this.selection.result(snapshot, buildOutput(tree, survey));
        }

        private ChunkSurvey surveyFinishedChunks(
            FinishedChunkSelection.Snapshot snapshot, ServerLevel level,
            Set<String> registeredBiomes
        ) {
            int minQuartY = QuartPos.fromBlock(level.getMinBuildHeight());
            int maxQuartY = QuartPos.fromBlock(level.getMaxBuildHeight() - 1);
            int surfaceQuartY = QuartPos.fromBlock(this.surfaceThresholdY);

            ChunkSurvey survey = new ChunkSurvey();
            for (FinishedChunkSelection.ReadyChunk ready : snapshot.ready()) {
                int chunkQuartX = ready.coordinate().x() * 4;
                int chunkQuartZ = ready.coordinate().z() * 4;
                for (int lqx = 0; lqx < 4; lqx += this.horizontalQuartStep) {
                    for (int lqz = 0; lqz < 4; lqz += this.horizontalQuartStep) {
                        int quartX = chunkQuartX + lqx;
                        int quartZ = chunkQuartZ + lqz;
                        for (int quartY = minQuartY; quartY <= maxQuartY;
                             quartY += this.verticalQuartStep) {
                            String biome = MinecraftProbeHelpers.biomeId(
                                ready.chunk().getNoiseBiome(quartX, quartY, quartZ)
                            );
                            boolean isSurface = quartY >= surfaceQuartY;
                            survey.record(biome, isSurface, registeredBiomes);
                        }
                    }
                }
            }
            return survey;
        }
    }

    static TreeAnalysis analyzeTree(
        List<Pair<Climate.ParameterPoint, Holder<Biome>>> entries
    ) {
        TreeAnalysis result = new TreeAnalysis();
        result.totalEntries = entries.size();

        Map<String, List<Climate.ParameterPoint>> biomeEntries = new LinkedHashMap<>();
        for (Pair<Climate.ParameterPoint, Holder<Biome>> entry : entries) {
            String biomeId = MinecraftProbeHelpers.biomeId(entry.getSecond());
            result.registeredBiomes.add(biomeId);
            biomeEntries.computeIfAbsent(biomeId, k -> new ArrayList<>()).add(entry.getFirst());
        }

        for (Map.Entry<String, List<Climate.ParameterPoint>> e : biomeEntries.entrySet()) {
            String biomeId = e.getKey();
            String ns = namespace(biomeId);
            List<Climate.ParameterPoint> points = e.getValue();

            int[] nsCounts = result.namespaceCounts
                .computeIfAbsent(ns, k -> new int[3]);
            nsCounts[0]++;
            nsCounts[1] += points.size();

            boolean hasConvention = false;
            boolean hasNonSurfaceDepth = false;
            boolean hasSurface = false;

            for (Climate.ParameterPoint p : points) {
                boolean isConv = RtfReachabilityCensusProbePack.isUndergroundConvention(p);
                if (isConv) {
                    hasConvention = true;
                    nsCounts[2]++;
                }
                float depthMin = Climate.unquantizeCoord(p.depth().min());
                if (depthMin > 0.0F) {
                    hasNonSurfaceDepth = true;
                } else {
                    hasSurface = true;
                }
            }

            if (hasConvention) {
                result.conventionBiomes.add(biomeId);
            } else if (hasNonSurfaceDepth && !hasSurface) {
                result.nonConventionUnderground.add(biomeId);
            }
        }

        Map<String, List<String>> pointCollisions = new LinkedHashMap<>();
        for (Pair<Climate.ParameterPoint, Holder<Biome>> entry : entries) {
            String key = parameterPointKey(entry.getFirst());
            pointCollisions.computeIfAbsent(key, k -> new ArrayList<>())
                .add(MinecraftProbeHelpers.biomeId(entry.getSecond()));
        }
        for (Map.Entry<String, List<String>> e : pointCollisions.entrySet()) {
            Set<String> unique = new TreeSet<>(e.getValue());
            if (unique.size() > 1) {
                result.duplicateRegistrations.add(new ArrayList<>(unique));
            }
        }

        return result;
    }

    private static String parameterPointKey(Climate.ParameterPoint p) {
        return p.temperature().min() + "," + p.temperature().max() + "|"
            + p.humidity().min() + "," + p.humidity().max() + "|"
            + p.continentalness().min() + "," + p.continentalness().max() + "|"
            + p.erosion().min() + "," + p.erosion().max() + "|"
            + p.depth().min() + "," + p.depth().max() + "|"
            + p.weirdness().min() + "," + p.weirdness().max() + "|"
            + p.offset();
    }

    private static String namespace(String biomeId) {
        int colon = biomeId.indexOf(':');
        return colon >= 0 ? biomeId.substring(0, colon) : "minecraft";
    }

    private static JsonObject buildOutput(TreeAnalysis tree, ChunkSurvey survey) {
        JsonObject data = new JsonObject();
        data.addProperty("authority", "composition-audit");

        // === Parameter tree structure ===
        JsonObject treeJson = new JsonObject();
        treeJson.addProperty("total_entries", tree.totalEntries);
        treeJson.addProperty("unique_biomes", tree.registeredBiomes.size());

        JsonObject nsJson = new JsonObject();
        for (Map.Entry<String, int[]> e : tree.namespaceCounts.entrySet()) {
            JsonObject ns = new JsonObject();
            ns.addProperty("biome_count", e.getValue()[0]);
            ns.addProperty("entry_count", e.getValue()[1]);
            ns.addProperty("underground_convention_entries", e.getValue()[2]);
            nsJson.add(e.getKey(), ns);
        }
        treeJson.add("namespaces", nsJson);
        data.add("parameter_tree", treeJson);

        // === Underground convention ===
        JsonObject ugJson = new JsonObject();
        ugJson.addProperty("candidate_count", tree.conventionBiomes.size());
        JsonArray convArr = new JsonArray();
        tree.conventionBiomes.forEach(convArr::add);
        ugJson.add("candidates", convArr);
        if (!tree.nonConventionUnderground.isEmpty()) {
            ugJson.addProperty("non_convention_underground_count",
                tree.nonConventionUnderground.size());
            JsonArray ncArr = new JsonArray();
            tree.nonConventionUnderground.forEach(ncArr::add);
            ugJson.add("non_convention_underground", ncArr);
        }
        data.add("underground_convention", ugJson);

        // === Duplicate registrations ===
        if (!tree.duplicateRegistrations.isEmpty()) {
            JsonArray dupArr = new JsonArray();
            for (List<String> group : tree.duplicateRegistrations) {
                JsonArray biomes = new JsonArray();
                group.forEach(biomes::add);
                dupArr.add(biomes);
            }
            data.add("duplicate_registrations", dupArr);
        }

        // === Finished-chunk survey ===
        JsonObject surveyJson = new JsonObject();
        surveyJson.addProperty("total_surface_samples", survey.surfaceTotal);
        surveyJson.addProperty("total_underground_samples", survey.undergroundTotal);
        surveyJson.addProperty("unique_surface_biomes", survey.surfaceBiomes.size());
        surveyJson.addProperty("unique_underground_biomes", survey.undergroundBiomes.size());
        surveyJson.addProperty("unique_total_observed", survey.allObserved.size());

        JsonObject observedJson = new JsonObject();
        for (Map.Entry<String, long[]> e : survey.counts.entrySet()) {
            JsonObject biomeObs = new JsonObject();
            biomeObs.addProperty("surface", e.getValue()[0]);
            biomeObs.addProperty("underground", e.getValue()[1]);
            biomeObs.addProperty("in_parameter_tree",
                tree.registeredBiomes.contains(e.getKey()));
            observedJson.add(e.getKey(), biomeObs);
        }
        surveyJson.add("observed_biomes", observedJson);

        if (!survey.outsideTree.isEmpty()) {
            JsonArray otArr = new JsonArray();
            survey.outsideTree.forEach(otArr::add);
            surveyJson.add("outside_parameter_tree", otArr);
        }

        Set<String> notObserved = new TreeSet<>(tree.registeredBiomes);
        notObserved.removeAll(survey.allObserved);
        surveyJson.addProperty("registered_not_observed_count", notObserved.size());
        if (!notObserved.isEmpty()) {
            JsonArray noArr = new JsonArray();
            notObserved.forEach(noArr::add);
            surveyJson.add("registered_not_observed", noArr);
        }

        data.add("finished_chunk_survey", surveyJson);

        // === Banding health ===
        JsonObject bandingJson = new JsonObject();
        bandingJson.addProperty("convention_candidates", tree.conventionBiomes.size());
        bandingJson.addProperty("unique_underground_observed", survey.undergroundBiomes.size());
        bandingJson.addProperty("unique_surface_observed", survey.surfaceBiomes.size());

        Set<String> undergroundOnly = new TreeSet<>(survey.undergroundBiomes);
        undergroundOnly.removeAll(survey.surfaceBiomes);
        bandingJson.addProperty("underground_only_count", undergroundOnly.size());
        if (!undergroundOnly.isEmpty()) {
            JsonArray uoArr = new JsonArray();
            undergroundOnly.forEach(uoArr::add);
            bandingJson.add("underground_only_biomes", uoArr);
        }

        if (!survey.surfaceBiomes.isEmpty()) {
            bandingJson.addProperty("underground_to_surface_diversity",
                (double) survey.undergroundBiomes.size() / survey.surfaceBiomes.size());
        }

        data.add("banding_health", bandingJson);

        return data;
    }

    static final class TreeAnalysis {
        int totalEntries;
        final Set<String> registeredBiomes = new TreeSet<>();
        final Map<String, int[]> namespaceCounts = new TreeMap<>();
        final List<String> conventionBiomes = new ArrayList<>();
        final List<String> nonConventionUnderground = new ArrayList<>();
        final List<List<String>> duplicateRegistrations = new ArrayList<>();
    }

    private static final class ChunkSurvey {
        long surfaceTotal;
        long undergroundTotal;
        final Set<String> surfaceBiomes = new TreeSet<>();
        final Set<String> undergroundBiomes = new TreeSet<>();
        final Set<String> allObserved = new TreeSet<>();
        final Set<String> outsideTree = new TreeSet<>();
        final Map<String, long[]> counts = new TreeMap<>();

        void record(String biome, boolean isSurface, Set<String> registeredBiomes) {
            allObserved.add(biome);
            long[] c = counts.computeIfAbsent(biome, k -> new long[2]);
            if (isSurface) {
                surfaceBiomes.add(biome);
                c[0]++;
                surfaceTotal++;
            } else {
                undergroundBiomes.add(biome);
                c[1]++;
                undergroundTotal++;
            }
            if (!registeredBiomes.contains(biome)) {
                outsideTree.add(biome);
            }
        }
    }
}
