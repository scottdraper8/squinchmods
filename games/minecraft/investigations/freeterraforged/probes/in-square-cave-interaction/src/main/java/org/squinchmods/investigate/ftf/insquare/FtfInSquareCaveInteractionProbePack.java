package org.squinchmods.investigate.ftf.insquare;

import java.lang.reflect.Method;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.Set;
import java.util.TreeMap;
import java.util.concurrent.atomic.LongAdder;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;

import net.minecraft.core.BlockPos;
import net.minecraft.core.Registry;
import net.minecraft.core.registries.Registries;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.level.levelgen.feature.ConfiguredFeature;
import net.minecraft.world.level.levelgen.placement.PlacedFeature;
import org.squinchmods.investigate.FinishedChunkSelection;
import org.squinchmods.investigate.ProbeExecution;
import org.squinchmods.investigate.ProbePack;
import org.squinchmods.investigate.ProbeRegistry;
import org.squinchmods.investigate.ProbeRequest;
import org.squinchmods.investigate.ProbeResult;

public final class FtfInSquareCaveInteractionProbePack implements ProbePack {
    @Override
    public void register() {
        ProbeRegistry.register(
            "squinch:ftf-in-square-cave-interaction",
            "1",
            InSquareCaveInteractionProbe::new
        );
    }

    private static final class InSquareCaveInteractionProbe implements ProbeExecution {
        private final FinishedChunkSelection selection;
        private final Set<String> featureIds;

        private InSquareCaveInteractionProbe(ProbeRequest request) {
            JsonObject config = request.config();
            this.selection = new FinishedChunkSelection(config, "ftf-in-square-cave-interaction");
            this.featureIds = Set.copyOf(strings(config, "feature_ids"));
        }

        @Override
        public ProbeResult tick(net.minecraft.server.MinecraftServer server) throws Exception {
            ServerLevel level = server.overworld();
            FinishedChunkSelection.Snapshot snapshot = this.selection.poll(level);
            if (snapshot == null) {
                return null;
            }
            Set<Long> chunks = snapshot.ready().stream()
                .map(ready -> ChunkPos.asLong(ready.coordinate().x(), ready.coordinate().z()))
                .collect(java.util.stream.Collectors.toUnmodifiableSet());

            Map<String, Aggregate> aggregates = new TreeMap<>();
            CaveInteractionTelemetry.stats().forEach((key, stats) -> {
                if (chunks.contains(key.chunk())
                    && (this.featureIds.isEmpty() || this.featureIds.contains(key.featureId()))) {
                    aggregates.computeIfAbsent(key.featureId(), ignored -> new Aggregate()).add(stats);
                }
            });

            JsonObject features = new JsonObject();
            aggregates.forEach((id, aggregate) -> features.add(id, aggregate.toJson()));
            JsonObject data = new JsonObject();
            data.addProperty("measurement_phase", "placement");
            data.addProperty("terminal_authority", "finished-chunk");
            data.addProperty("selected_chunk_count", chunks.size());
            data.addProperty("observed_feature_count", aggregates.size());
            data.add("features", features);
            data.add("registry_census", registryCensus(level));
            return this.selection.result(snapshot, data);
        }
    }

    private static JsonObject registryCensus(ServerLevel level) throws Exception {
        Registry<PlacedFeature> placedRegistry = level.registryAccess()
            .registryOrThrow(Registries.PLACED_FEATURE);
        Registry<ConfiguredFeature<?, ?>> configuredRegistry = level.registryAccess()
            .registryOrThrow(Registries.CONFIGURED_FEATURE);
        Class<?> classifierClass = Class.forName(
            "etcodehome.freeterraforged.world.worldgen.feature.placement.SurfacePlacementClassifier"
        );
        Method classify = classifierClass.getDeclaredMethod(
            "classify",
            PlacedFeature.class,
            Optional.class,
            net.minecraft.core.HolderLookup.Provider.class
        );
        classify.setAccessible(true);

        List<CensusEntry> entries = new ArrayList<>();
        List<CensusEntry> unsafeEntries = new ArrayList<>();
        Map<String, List<CensusEntry>> byConfiguredFeature = new TreeMap<>();
        int rescueEligible = 0;
        int rescueEligibleUnsafe = 0;
        for (ResourceLocation placedId : placedRegistry.keySet().stream().sorted().toList()) {
            PlacedFeature feature = placedRegistry.get(placedId);
            Object classification = classify.invoke(null, feature, Optional.of(placedId), level.registryAccess());
            Method eligibleMethod = classification.getClass().getDeclaredMethod("eligible");
            eligibleMethod.setAccessible(true);
            boolean eligible = (Boolean)eligibleMethod.invoke(classification);
            Pr202FeatureAnalysis.Result pr202 = Pr202FeatureAnalysis.inspect(feature);
            Pr202FeatureAnalysis.Result intrinsic = Pr202FeatureAnalysis.inspectIntrinsic(feature);
            ResourceLocation configuredId = configuredRegistry.getKey(feature.feature().value());
            CensusEntry entry = new CensusEntry(
                placedId.toString(),
                configuredId == null ? "unregistered" : configuredId.toString(),
                eligible,
                pr202.unsafe(),
                pr202.reason(),
                intrinsic.unsafe(),
                intrinsic.reason(),
                feature.placement().stream().map(modifier -> modifier.getClass().getSimpleName()).toList()
            );
            if (eligible) {
                entries.add(entry);
                rescueEligible++;
                if (pr202.unsafe()) {
                    rescueEligibleUnsafe++;
                }
            }
            if (pr202.unsafe()) {
                unsafeEntries.add(entry);
            }
            byConfiguredFeature.computeIfAbsent(entry.configuredFeatureId(), ignored -> new ArrayList<>())
                .add(entry);
        }

        JsonArray eligibleFeatures = new JsonArray();
        entries.forEach(entry -> eligibleFeatures.add(entry.toJson()));
        JsonArray unsafeFeatures = new JsonArray();
        unsafeEntries.forEach(entry -> unsafeFeatures.add(entry.toJson()));
        JsonArray divergentCacheGroups = new JsonArray();
        byConfiguredFeature.forEach((configuredId, group) -> {
            if (group.size() < 2) {
                return;
            }
            boolean first = group.getFirst().intrinsicUnsafe();
            if (group.stream().anyMatch(entry -> entry.intrinsicUnsafe() != first)) {
                JsonObject value = new JsonObject();
                value.addProperty("configured_feature", configuredId);
                JsonArray placedFeatures = new JsonArray();
                group.forEach(entry -> placedFeatures.add(entry.toJson()));
                value.add("placed_features", placedFeatures);
                divergentCacheGroups.add(value);
            }
        });

        JsonObject result = new JsonObject();
        result.addProperty("placed_feature_count", placedRegistry.size());
        result.addProperty("rescue_eligible_count", rescueEligible);
        result.addProperty("rescue_eligible_pr202_unsafe_count", rescueEligibleUnsafe);
        result.add("rescue_eligible_features", eligibleFeatures);
        result.addProperty("pr202_unsafe_count", unsafeEntries.size());
        result.add("pr202_unsafe_features", unsafeFeatures);
        result.addProperty("configured_feature_cache_divergence_group_count", divergentCacheGroups.size());
        result.add("configured_feature_cache_divergence_groups", divergentCacheGroups);
        return result;
    }

    private static List<String> strings(JsonObject config, String key) {
        if (!config.has(key)) {
            return List.of();
        }
        List<String> result = new ArrayList<>();
        for (JsonElement element : config.getAsJsonArray(key)) {
            result.add(element.getAsString());
        }
        return result;
    }

    private static JsonObject counts(Map<Integer, Long> values) {
        JsonObject result = new JsonObject();
        values.forEach((key, value) -> result.addProperty(Integer.toString(key), value));
        return result;
    }

    private static <K> void merge(Map<K, Long> target, Map<K, LongAdder> source) {
        source.forEach((key, value) -> target.merge(key, value.sum(), Long::sum));
    }

    private static final class Aggregate {
        private long inSquareOutputs;
        private long inSquareCalls;
        private long inSquareEdgeOutputs;
        private long inSquareOutsideVanillaChunk;
        private long failedScanRescueEntries;
        private long preBudgetRejectedEntries;
        private long budgetSkippedEntries;
        private long scheduledColumnSearches;
        private long physicalColumnScans;
        private long cachedColumnReuses;
        private long scanPredicateChecks;
        private long surfaceRechecks;
        private long discoveredSurfaces;
        private long rescueNanos;
        private long scanNanos;
        private long rescueSuccesses;
        private long rescuedBiomeChecks;
        private long rescuedBiomePasses;
        private long rescuedConfiguredFeatureCalls;
        private long rescuedConfiguredFeatureSuccesses;
        private long rescuedPipelineMismatches;
        private long rescueEdgeColumns;
        private final Map<Integer, Long> inSquareDx = new TreeMap<>();
        private final Map<Integer, Long> inSquareDz = new TreeMap<>();
        private final Map<Integer, Long> rescueLocalX = new TreeMap<>();
        private final Map<Integer, Long> rescueLocalZ = new TreeMap<>();
        private final Map<Integer, Long> rescueEntryY = new TreeMap<>();
        private final Map<Integer, Long> scheduledOriginY = new TreeMap<>();
        private final Map<Integer, Long> rescueY = new TreeMap<>();
        private final Map<Long, Long> rescuePositions = new TreeMap<>();

        private void add(CaveInteractionTelemetry.Stats stats) {
            this.inSquareCalls += stats.inSquareCalls.sum();
            this.inSquareOutputs += stats.inSquareOutputs.sum();
            this.inSquareEdgeOutputs += stats.inSquareEdgeOutputs.sum();
            this.inSquareOutsideVanillaChunk += stats.inSquareOutsideVanillaChunk.sum();
            this.failedScanRescueEntries += stats.failedScanRescueEntries.sum();
            this.preBudgetRejectedEntries += stats.preBudgetRejectedEntries.sum();
            this.budgetSkippedEntries += stats.budgetSkippedEntries.sum();
            this.scheduledColumnSearches += stats.scheduledColumnSearches.sum();
            this.physicalColumnScans += stats.physicalColumnScans.sum();
            this.cachedColumnReuses += stats.cachedColumnReuses.sum();
            this.scanPredicateChecks += stats.scanPredicateChecks.sum();
            this.surfaceRechecks += stats.surfaceRechecks.sum();
            this.discoveredSurfaces += stats.discoveredSurfaces.sum();
            this.rescueNanos += stats.rescueNanos.sum();
            this.scanNanos += stats.scanNanos.sum();
            this.rescueSuccesses += stats.rescueSuccesses.sum();
            this.rescuedBiomeChecks += stats.rescuedBiomeChecks.sum();
            this.rescuedBiomePasses += stats.rescuedBiomePasses.sum();
            this.rescuedConfiguredFeatureCalls += stats.rescuedConfiguredFeatureCalls.sum();
            this.rescuedConfiguredFeatureSuccesses += stats.rescuedConfiguredFeatureSuccesses.sum();
            this.rescuedPipelineMismatches += stats.rescuedPipelineMismatches.sum();
            this.rescueEdgeColumns += stats.rescueEdgeColumns.sum();
            merge(this.inSquareDx, stats.inSquareDx);
            merge(this.inSquareDz, stats.inSquareDz);
            merge(this.rescueLocalX, stats.rescueLocalX);
            merge(this.rescueLocalZ, stats.rescueLocalZ);
            merge(this.rescueEntryY, stats.rescueEntryY);
            merge(this.scheduledOriginY, stats.scheduledOriginY);
            merge(this.rescueY, stats.rescueY);
            merge(this.rescuePositions, stats.rescuePositions);
        }

        private JsonObject toJson() {
            JsonObject result = new JsonObject();
            result.addProperty("in_square_calls", this.inSquareCalls);
            result.addProperty("in_square_outputs", this.inSquareOutputs);
            result.addProperty("in_square_edge_outputs", this.inSquareEdgeOutputs);
            result.addProperty("in_square_outside_vanilla_chunk", this.inSquareOutsideVanillaChunk);
            result.addProperty("failed_scan_rescue_entries", this.failedScanRescueEntries);
            result.addProperty("pre_budget_rejected_entries", this.preBudgetRejectedEntries);
            result.addProperty("budget_skipped_entries", this.budgetSkippedEntries);
            result.addProperty("scheduled_column_searches", this.scheduledColumnSearches);
            result.addProperty("physical_column_scans", this.physicalColumnScans);
            result.addProperty("cached_column_reuses", this.cachedColumnReuses);
            result.addProperty("scan_predicate_checks", this.scanPredicateChecks);
            result.addProperty("surface_rechecks", this.surfaceRechecks);
            result.addProperty("discovered_surfaces", this.discoveredSurfaces);
            result.addProperty("rescue_elapsed_nanos", this.rescueNanos);
            result.addProperty("physical_scan_elapsed_nanos", this.scanNanos);
            result.addProperty("rescue_successes", this.rescueSuccesses);
            result.addProperty("rescued_biome_checks", this.rescuedBiomeChecks);
            result.addProperty("rescued_biome_passes", this.rescuedBiomePasses);
            result.addProperty("rescued_configured_feature_calls", this.rescuedConfiguredFeatureCalls);
            result.addProperty("rescued_configured_feature_successes", this.rescuedConfiguredFeatureSuccesses);
            result.addProperty("rescued_pipeline_mismatches", this.rescuedPipelineMismatches);
            result.addProperty("rescue_edge_columns", this.rescueEdgeColumns);
            result.add("in_square_dx_histogram", counts(this.inSquareDx));
            result.add("in_square_dz_histogram", counts(this.inSquareDz));
            result.add("rescue_local_x_histogram", counts(this.rescueLocalX));
            result.add("rescue_local_z_histogram", counts(this.rescueLocalZ));
            result.add("failed_scan_origin_y_histogram", counts(this.rescueEntryY));
            result.add("scheduled_search_origin_y_histogram", counts(this.scheduledOriginY));
            result.add("rescue_y_histogram", counts(this.rescueY));
            JsonArray positions = new JsonArray();
            this.rescuePositions.forEach((packed, count) -> {
                BlockPos position = BlockPos.of(packed);
                JsonObject entry = new JsonObject();
                entry.addProperty("x", position.getX());
                entry.addProperty("y", position.getY());
                entry.addProperty("z", position.getZ());
                entry.addProperty("count", count);
                positions.add(entry);
            });
            result.add("rescue_positions", positions);
            return result;
        }
    }

    private record CensusEntry(
        String placedFeatureId,
        String configuredFeatureId,
        boolean rescueEligible,
        boolean pr202Unsafe,
        String pr202Reason,
        boolean intrinsicUnsafe,
        String intrinsicReason,
        List<String> modifiers
    ) {
        private JsonObject toJson() {
            JsonObject result = new JsonObject();
            result.addProperty("placed_feature", this.placedFeatureId);
            result.addProperty("configured_feature", this.configuredFeatureId);
            result.addProperty("rescue_eligible", this.rescueEligible);
            result.addProperty("pr202_unsafe", this.pr202Unsafe);
            result.addProperty("pr202_reason", this.pr202Reason);
            result.addProperty("intrinsic_unsafe", this.intrinsicUnsafe);
            result.addProperty("intrinsic_reason", this.intrinsicReason);
            JsonArray pipeline = new JsonArray();
            this.modifiers.forEach(pipeline::add);
            result.add("placement_modifiers", pipeline);
            return result;
        }
    }
}
