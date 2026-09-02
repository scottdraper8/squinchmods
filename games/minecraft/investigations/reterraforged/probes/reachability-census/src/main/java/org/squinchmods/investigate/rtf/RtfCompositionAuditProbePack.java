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
import org.squinchmods.investigate.ProbePhase;
import org.squinchmods.investigate.ProbeRegistry;
import org.squinchmods.investigate.ProbeRequest;
import org.squinchmods.investigate.ProbeResult;
import org.squinchmods.investigate.TerminalState;
import org.squinchmods.investigate.rtf.mixin.AccessorMultiNoiseBiomeSource;
import raccoonman.reterraforged.world.worldgen.biome.UndergroundBiomeBanding;
import raccoonman.reterraforged.concurrent.Resource;
import raccoonman.reterraforged.world.worldgen.GeneratorContext;
import raccoonman.reterraforged.world.worldgen.RTFRandomState;
import raccoonman.reterraforged.world.worldgen.cell.Cell;
import raccoonman.reterraforged.world.worldgen.runtime.TerraForgedChunkGenerator;
import raccoonman.reterraforged.world.worldgen.runtime.WorldgenBiomeSelection;
import raccoonman.reterraforged.world.worldgen.runtime.WorldgenPlan;
import raccoonman.reterraforged.world.worldgen.runtime.WorldgenPlans;

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

            BiomeSource runtimeSource = level.getChunkSource().getGenerator().getBiomeSource();
            BiomeSource acquisitionSource = level.getChunkSource().getGenerator()
                instanceof TerraForgedChunkGenerator generator
                    ? generator.acquisitionBiomeSource()
                    : runtimeSource;
            if (!(acquisitionSource instanceof MultiNoiseBiomeSource mnbs)) {
                JsonObject data = new JsonObject();
                data.addProperty(
                    "error",
                    "Acquisition BiomeSource is not MultiNoiseBiomeSource: "
                        + acquisitionSource.getClass().getName()
                );
                return ProbeResult.complete(
                    TerminalState.ERROR, ProbePhase.FINISHED_CHUNK, data, snapshot.ready().size()
                );
            }

            Climate.ParameterList<Holder<Biome>> parameters =
                ((AccessorMultiNoiseBiomeSource) (Object) mnbs).invokeParameters();
            List<Pair<Climate.ParameterPoint, Holder<Biome>>> rawEntries = parameters.values();

            TreeAnalysis tree = analyzeTree(rawEntries);
            runtimeSource.possibleBiomes().stream()
                .map(MinecraftProbeHelpers::biomeId)
                .forEach(tree.possibleBiomes::add);
            WorldgenPlan plan = level.getChunkSource().getGenerator() instanceof TerraForgedChunkGenerator generator
                ? generator.plan().orElse(null)
                : ((RTFRandomState) (Object) level.getChunkSource().randomState()).plan();
            GeneratorContext generatorContext = ((RTFRandomState) (Object) level.getChunkSource().randomState())
                .generatorContext();
            ChunkSurvey survey = surveyFinishedChunks(
                snapshot, level, tree.registeredBiomes, plan, generatorContext
            );

            return this.selection.result(snapshot, buildOutput(tree, survey, plan));
        }

        private ChunkSurvey surveyFinishedChunks(
            FinishedChunkSelection.Snapshot snapshot, ServerLevel level,
            Set<String> registeredBiomes,
            WorldgenPlan plan,
            GeneratorContext generatorContext
        ) {
            int minQuartY = QuartPos.fromBlock(level.getMinBuildHeight());
            int maxQuartY = QuartPos.fromBlock(level.getMaxBuildHeight() - 1);
            int surfaceQuartY = QuartPos.fromBlock(this.surfaceThresholdY);

            ChunkSurvey survey = new ChunkSurvey();
            Climate.Sampler sampler = level.getChunkSource().randomState().sampler();
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
                            if (plan != null && generatorContext != null
                                && !plan.providerSelection().providers().isEmpty()) {
                                Climate.TargetPoint target = sampler.sample(quartX, quartY, quartZ);
                                long cellX;
                                long cellZ;
                                try (Resource<Cell> resource = Cell.getResource()) {
                                    Cell cell = resource.get().reset();
                                    generatorContext.lookup.applyCell(
                                        cell, QuartPos.toBlock(quartX), QuartPos.toBlock(quartZ), false, true
                                    );
                                    cellX = cell.biomeRegionX;
                                    cellZ = cell.biomeRegionZ;
                                }
                                WorldgenPlans.ProviderResult selection = plan.providerSelection()
                                    .resolve(cellX, cellZ, target)
                                    .orElseThrow();
                                Holder<Biome> resolved = WorldgenBiomeSelection.resolve(
                                    plan, quartX, quartY, quartZ, sampler
                                );
                                survey.recordSelection(selection, resolved, biome);
                            }
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
                UndergroundBiomeBanding.CandidateRole role = UndergroundBiomeBanding.classify(
                    p, false
                );
                boolean isCandidate = role == UndergroundBiomeBanding.CandidateRole.SHALLOW_CAVE
                    || role == UndergroundBiomeBanding.CandidateRole.DEEP_CAVE;
                if (isCandidate) {
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

    private static JsonObject buildOutput(
        TreeAnalysis tree,
        ChunkSurvey survey,
        WorldgenPlan plan
    ) {
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

        JsonObject possibleJson = new JsonObject();
        possibleJson.addProperty("biome_count", tree.possibleBiomes.size());
        JsonObject possibleNamespaces = new JsonObject();
        Map<String, Integer> possibleNamespaceCounts = new TreeMap<>();
        tree.possibleBiomes.forEach(biome -> possibleNamespaceCounts.merge(namespace(biome), 1, Integer::sum));
        possibleNamespaceCounts.forEach(possibleNamespaces::addProperty);
        possibleJson.add("namespaces", possibleNamespaces);
        JsonArray possibleBiomes = new JsonArray();
        tree.possibleBiomes.forEach(possibleBiomes::add);
        possibleJson.add("biomes", possibleBiomes);
        data.add("biome_source_possible", possibleJson);

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

        if (plan != null) {
            JsonObject providerJson = new JsonObject();
            providerJson.addProperty("state", plan.providerSelection().descriptor().state().name().toLowerCase());
            providerJson.addProperty("mechanism", plan.providerSelection().descriptor().mechanism());
            providerJson.addProperty("provider_count", plan.providerSelection().providers().size());
            providerJson.addProperty("has_fallback", plan.providerSelection().fallback().isPresent());
            providerJson.addProperty("has_deferred_placeholder", plan.providerSelection().deferredPlaceholder().isPresent());
            JsonArray providers = new JsonArray();
            for (WorldgenPlans.ProviderDomain provider : plan.providerSelection().providers()) {
                JsonObject value = new JsonObject();
                value.addProperty("id", provider.id().toString());
                value.addProperty("weight", provider.weight());
                value.addProperty("registration_order", provider.registrationOrder());
                value.addProperty("candidate_count", provider.candidates().values().size());
                providers.add(value);
            }
            providerJson.add("providers", providers);
            data.add("provider_plan", providerJson);
            data.add("plan_diagnostics", plan.diagnostics().toJson());
        }

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

        if (survey.selectionSamples > 0) {
            JsonObject selectionJson = new JsonObject();
            selectionJson.addProperty("authority", "direct-random-state-sampler-diagnostic");
            selectionJson.addProperty("samples", survey.selectionSamples);
            selectionJson.addProperty("finished_palette_agreements", survey.finishedPaletteAgreements);
            selectionJson.addProperty("finished_palette_disagreements", survey.finishedPaletteDisagreements);
            selectionJson.add("selected_regions", counts(survey.selectedRegions));
            selectionJson.add("original_winners", counts(survey.originalWinners));
            selectionJson.add("banded_winners", counts(survey.bandedWinners));
            selectionJson.add("fallback_reasons", counts(survey.fallbackReasons));
            data.add("selection_audit", selectionJson);
        }

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

    private static JsonObject counts(Map<String, Long> counts) {
        JsonObject result = new JsonObject();
        counts.forEach(result::addProperty);
        return result;
    }

    static final class TreeAnalysis {
        int totalEntries;
        final Set<String> registeredBiomes = new TreeSet<>();
        final Set<String> possibleBiomes = new TreeSet<>();
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
        long selectionSamples;
        long finishedPaletteAgreements;
        long finishedPaletteDisagreements;
        final Map<String, Long> selectedRegions = new TreeMap<>();
        final Map<String, Long> originalWinners = new TreeMap<>();
        final Map<String, Long> bandedWinners = new TreeMap<>();
        final Map<String, Long> fallbackReasons = new TreeMap<>();

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

        void recordSelection(
            WorldgenPlans.ProviderResult selection,
            Holder<Biome> resolved,
            String finishedBiome
        ) {
            this.selectionSamples++;
            this.selectedRegions.merge(selection.domain().toString(), 1L, Long::sum);
            if (selection.usedFallback()) {
                this.fallbackReasons.merge("deferred_default", 1L, Long::sum);
            }

            String original = MinecraftProbeHelpers.biomeId(selection.biome());
            String banded = MinecraftProbeHelpers.biomeId(resolved);
            this.originalWinners.merge(original, 1L, Long::sum);
            this.bandedWinners.merge(banded, 1L, Long::sum);
            if (banded.equals(finishedBiome)) {
                this.finishedPaletteAgreements++;
            } else {
                this.finishedPaletteDisagreements++;
            }
        }
    }
}
