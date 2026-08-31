package org.squinchmods.investigate.rtf;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeMap;
import java.util.TreeSet;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;

import net.minecraft.core.Holder;
import net.minecraft.core.Registry;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.core.registries.Registries;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.biome.Biome;
import net.minecraft.world.level.levelgen.GenerationStep;
import net.minecraft.world.level.levelgen.feature.ConfiguredFeature;
import net.minecraft.world.level.levelgen.placement.PlacedFeature;
import net.minecraft.world.level.levelgen.placement.PlacementModifier;
import org.squinchmods.investigate.ProbeExecution;
import org.squinchmods.investigate.ProbePack;
import org.squinchmods.investigate.ProbePhase;
import org.squinchmods.investigate.ProbeRegistry;
import org.squinchmods.investigate.ProbeRequest;
import org.squinchmods.investigate.ProbeResult;
import org.squinchmods.investigate.TerminalState;
import raccoonman.reterraforged.world.worldgen.runtime.TerraForgedChunkGenerator;
import raccoonman.reterraforged.world.worldgen.runtime.WorldgenPlan;
import raccoonman.reterraforged.world.worldgen.runtime.WorldgenPlans;

/** Records the final biome feature graph after loader and mod composition has completed. */
public final class FeatureGraphCensusProbePack implements ProbePack {
    @Override
    public void register() {
        ProbeRegistry.register("squinch:rtf-feature-graph-census", "1", FeatureGraphCensus::new);
    }

    private static final class FeatureGraphCensus implements ProbeExecution {
        private FeatureGraphCensus(ProbeRequest request) {
        }

        @Override
        public ProbeResult tick(MinecraftServer server) {
            ServerLevel level = server.overworld();
            Registry<Biome> biomes = level.registryAccess().registryOrThrow(Registries.BIOME);
            Registry<PlacedFeature> placedFeatures =
                level.registryAccess().registryOrThrow(Registries.PLACED_FEATURE);
            if (!(level.getChunkSource().getGenerator() instanceof TerraForgedChunkGenerator generator)) {
                JsonObject data = new JsonObject();
                data.addProperty("error", "Selected generator is not the FTF-owned runtime root");
                return ProbeResult.complete(TerminalState.FAIL, ProbePhase.GENERATION, data, 0);
            }
            WorldgenPlan worldgenPlan = generator.plan().orElse(null);
            if (worldgenPlan == null) {
                JsonObject data = new JsonObject();
                data.addProperty("error", "FTF generator has no active worldgen plan");
                return ProbeResult.complete(TerminalState.FAIL, ProbePhase.GENERATION, data, 0);
            }
            WorldgenPlans.PlacedFeatures plan = worldgenPlan.placedFeatures();
            Census census = new Census(placedFeatures, plan);

            biomes.holders()
                .sorted(Comparator.comparing(holder -> holder.key().location().toString()))
                .forEach(holder -> census.inspectBiome(holder.key().location().toString(), holder, plan));

            JsonObject data = census.toJson();
            data.add("capability_report", worldgenPlan.report().toJson());
            return ProbeResult.complete(
                TerminalState.PASS,
                ProbePhase.GENERATION,
                data,
                census.biomeCount
            );
        }
    }

    private static final class Census {
        private final Set<String> registeredIds = new TreeSet<>();
        private final Set<String> activeIds = new TreeSet<>();
        private final Map<String, ContractGroup> contracts = new TreeMap<>();
        private final Map<String, Integer> namespaceRegistryCounts = new TreeMap<>();
        private final Map<String, Integer> namespaceActiveCounts = new TreeMap<>();
        private final JsonArray biomesJson = new JsonArray();
        private final JsonArray duplicateMemberships = new JsonArray();
        private final WorldgenPlans.PlacedFeatures plan;
        private int biomeCount;
        private int totalOccurrences;
        private int duplicateOccurrenceCount;

        private Census(Registry<PlacedFeature> registry, WorldgenPlans.PlacedFeatures plan) {
            this.plan = plan;
            registry.keySet().stream()
                .map(ResourceLocation::toString)
                .sorted()
                .forEach(id -> {
                    this.registeredIds.add(id);
                    this.namespaceRegistryCounts.merge(namespace(id), 1, Integer::sum);
                });
        }

        private void inspectBiome(
            String biomeId,
            Holder.Reference<Biome> biome,
            WorldgenPlans.PlacedFeatures plan
        ) {
            this.biomeCount++;
            JsonObject biomeJson = new JsonObject();
            biomeJson.addProperty("biome", biomeId);
            JsonArray stepsJson = new JsonArray();
            Map<String, List<JsonObject>> occurrencesById = new TreeMap<>();
            Set<String> uniqueBiomeIds = new TreeSet<>();

            int stepCount = plan.pipelines().stream()
                .filter(pipeline -> pipeline.biome().equals(biome.key()))
                .mapToInt(WorldgenPlans.PlacedFeaturePipeline::generationStep)
                .max()
                .orElse(-1) + 1;
            for (int stepIndex = 0; stepIndex < stepCount; stepIndex++) {
                JsonObject stepJson = new JsonObject();
                stepJson.addProperty("step_index", stepIndex);
                stepJson.addProperty("step", stepName(stepIndex));
                JsonArray featuresJson = new JsonArray();
                int occurrenceIndex = 0;
                for (Holder<PlacedFeature> holder : plan.forBiome(biome, stepIndex)) {
                    String id = holderId(holder);
                    PlacedFeature placed = holder.value();
                    Contract contract = Contract.of(placed);
                    JsonObject occurrence = occurrence(id, stepIndex, occurrenceIndex, contract);
                    featuresJson.add(occurrence);
                    occurrencesById.computeIfAbsent(id, ignored -> new ArrayList<>()).add(occurrence);
                    uniqueBiomeIds.add(id);
                    this.activeIds.add(id);
                    this.namespaceActiveCounts.merge(namespace(id), 1, Integer::sum);
                    this.contracts.computeIfAbsent(contract.key, ignored -> new ContractGroup(contract))
                        .ids.add(id);
                    this.totalOccurrences++;
                    occurrenceIndex++;
                }
                stepJson.add("features", featuresJson);
                if (occurrenceIndex > 0) {
                    stepsJson.add(stepJson);
                }
            }

            for (Map.Entry<String, List<JsonObject>> entry : occurrencesById.entrySet()) {
                if (entry.getValue().size() > 1) {
                    this.duplicateOccurrenceCount += entry.getValue().size() - 1;
                    JsonObject duplicate = new JsonObject();
                    duplicate.addProperty("biome", biomeId);
                    duplicate.addProperty("feature_id", entry.getKey());
                    duplicate.addProperty("occurrence_count", entry.getValue().size());
                    JsonArray locations = new JsonArray();
                    for (JsonObject occurrence : entry.getValue()) {
                        JsonObject location = new JsonObject();
                        location.addProperty("step_index", occurrence.get("step_index").getAsInt());
                        location.addProperty("step", occurrence.get("step").getAsString());
                        location.addProperty("occurrence_index", occurrence.get("occurrence_index").getAsInt());
                        locations.add(location);
                    }
                    duplicate.add("locations", locations);
                    this.duplicateMemberships.add(duplicate);
                }
            }

            biomeJson.addProperty("unique_feature_ids", uniqueBiomeIds.size());
            biomeJson.addProperty("feature_occurrences", totalOccurrences(occurrencesById));
            biomeJson.add("steps", stepsJson);
            this.biomesJson.add(biomeJson);
        }

        private JsonObject toJson() {
            JsonObject data = new JsonObject();
            data.addProperty("authority", "ftf-owned-typed-feature-plan");
            data.addProperty("scope", "all-registered-biomes-and-compiled-feature-occurrences");
            data.addProperty("plan_state", this.plan.descriptor().state().name().toLowerCase());
            data.addProperty("plan_mechanism", this.plan.descriptor().mechanism());
            data.addProperty("compiled_pipeline_count", this.plan.pipelines().size());
            data.addProperty("compiled_schedule_step_count", this.plan.steps().size());
            data.addProperty("ore_plan_active_features", this.plan.ores().activeFeatures());
            data.addProperty("ore_plan_standard_ores", this.plan.ores().standardOres());
            data.addProperty("ore_plan_dynamic_transforms", this.plan.ores().verticalTransforms().size());
            data.addProperty("ore_plan_delegated_features", this.plan.ores().delegatedFeatures());
            data.addProperty("ore_plan_failure_count", this.plan.ores().failures().size());
            data.addProperty("biome_count", this.biomeCount);
            data.addProperty("placed_feature_registry_count", this.registeredIds.size());
            data.addProperty("active_unique_feature_count", this.activeIds.size());
            data.addProperty("active_feature_occurrence_count", this.totalOccurrences);
            data.addProperty("duplicate_occurrence_count", this.duplicateOccurrenceCount);
            data.add("namespace_registry_counts", integerObject(this.namespaceRegistryCounts));
            data.add("namespace_active_occurrence_counts", integerObject(this.namespaceActiveCounts));
            data.add("biomes", this.biomesJson);
            data.add("duplicate_memberships", this.duplicateMemberships);

            JsonArray unreferenced = new JsonArray();
            this.registeredIds.stream()
                .filter(id -> !this.activeIds.contains(id))
                .forEach(unreferenced::add);
            data.addProperty("unreferenced_registry_entry_count", unreferenced.size());
            data.add("unreferenced_registry_entries", unreferenced);

            JsonArray contractCandidates = new JsonArray();
            this.contracts.values().stream()
                .filter(group -> group.ids.size() > 1)
                .sorted(Comparator.comparing(group -> group.contract.key))
                .forEach(group -> contractCandidates.add(group.toJson()));
            data.addProperty("same_contract_candidate_group_count", contractCandidates.size());
            data.add("same_contract_candidates", contractCandidates);

            JsonObject interpretation = new JsonObject();
            interpretation.addProperty(
                "unreferenced_registry_entries",
                "candidate_absences_only_registry_presence_does_not_prove_a_modifier_removal"
            );
            interpretation.addProperty(
                "same_contract_candidates",
                "cross_id_contract_matches_replacement_candidates_require_pre_modifier_provenance"
            );
            interpretation.addProperty(
                "duplicate_memberships",
                "same_placed_feature_id_occurring_multiple_times_in_one_final_biome_graph"
            );
            data.add("interpretation", interpretation);
            return data;
        }

        private static int totalOccurrences(Map<String, List<JsonObject>> occurrencesById) {
            return occurrencesById.values().stream().mapToInt(List::size).sum();
        }

        private static JsonObject occurrence(String id, int stepIndex, int occurrenceIndex, Contract contract) {
            JsonObject result = new JsonObject();
            result.addProperty("id", id);
            result.addProperty("step_index", stepIndex);
            result.addProperty("step", stepName(stepIndex));
            result.addProperty("occurrence_index", occurrenceIndex);
            result.addProperty("configured_feature_type", contract.configuredFeatureType);
            result.add("placement_modifier_types", strings(contract.placementModifierTypes));
            result.addProperty("contract_key", contract.key);
            return result;
        }

        private static String holderId(Holder<PlacedFeature> holder) {
            return holder.unwrapKey()
                .map(key -> key.location().toString())
                .orElse("[unregistered]");
        }

        private static String stepName(int index) {
            GenerationStep.Decoration[] values = GenerationStep.Decoration.values();
            return index >= 0 && index < values.length ? values[index].name() : "UNKNOWN_" + index;
        }

        private static String namespace(String id) {
            int colon = id.indexOf(':');
            return colon < 0 ? "[unregistered]" : id.substring(0, colon);
        }
    }

    private static final class Contract {
        private final String key;
        private final String configuredFeatureType;
        private final List<String> placementModifierTypes;

        private Contract(String key, String configuredFeatureType, List<String> placementModifierTypes) {
            this.key = key;
            this.configuredFeatureType = configuredFeatureType;
            this.placementModifierTypes = placementModifierTypes;
        }

        private static Contract of(PlacedFeature placed) {
            ConfiguredFeature<?, ?> configured = placed.feature().value();
            ResourceLocation featureKey = BuiltInRegistries.FEATURE.getKey(configured.feature());
            String configuredType = featureKey == null ? "[unregistered]" : featureKey.toString();
            List<String> modifiers = placed.placement().stream()
                .map(PlacementModifier::type)
                .map(BuiltInRegistries.PLACEMENT_MODIFIER_TYPE::getKey)
                .map(key -> key == null ? "[unregistered]" : key.toString())
                .toList();
            String key = configuredType + "|" + String.join(",", modifiers);
            return new Contract(key, configuredType, modifiers);
        }
    }

    private static final class ContractGroup {
        private final Contract contract;
        private final Set<String> ids = new TreeSet<>();

        private ContractGroup(Contract contract) {
            this.contract = contract;
        }

        private JsonObject toJson() {
            JsonObject result = new JsonObject();
            result.addProperty("contract_key", this.contract.key);
            result.addProperty("configured_feature_type", this.contract.configuredFeatureType);
            result.add("placement_modifier_types", strings(this.contract.placementModifierTypes));
            JsonArray ids = new JsonArray();
            this.ids.forEach(ids::add);
            result.add("feature_ids", ids);
            result.addProperty(
                "cross_namespace",
                this.ids.stream().map(Census::namespace).distinct().count() > 1
            );
            return result;
        }
    }

    private static JsonObject integerObject(Map<String, Integer> values) {
        JsonObject result = new JsonObject();
        values.forEach(result::addProperty);
        return result;
    }

    private static JsonArray strings(List<String> values) {
        JsonArray result = new JsonArray();
        values.forEach(result::add);
        return result;
    }
}
