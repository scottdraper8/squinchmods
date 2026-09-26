package org.squinchmods.investigate.ftf;

import java.io.IOException;
import java.io.InputStream;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HexFormat;
import java.util.IdentityHashMap;
import java.util.LinkedHashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeMap;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.mojang.serialization.Codec;
import com.mojang.serialization.DataResult;
import com.mojang.serialization.JsonOps;

import net.minecraft.core.Holder;
import net.minecraft.core.HolderSet;
import net.minecraft.core.Registry;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.core.registries.Registries;
import net.minecraft.resources.RegistryOps;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.packs.resources.Resource;
import net.minecraft.world.level.biome.Biome;
import net.minecraft.world.level.biome.BiomeGenerationSettings;
import net.minecraft.world.level.biome.BiomeSource;
import net.minecraft.world.level.biome.Climate;
import net.minecraft.world.level.chunk.ChunkGenerator;
import net.minecraft.world.level.levelgen.DensityFunction;
import net.minecraft.world.level.levelgen.GenerationStep;
import net.minecraft.world.level.levelgen.NoiseBasedChunkGenerator;
import net.minecraft.world.level.levelgen.NoiseGeneratorSettings;
import net.minecraft.world.level.levelgen.NoiseRouter;
import net.minecraft.world.level.levelgen.SurfaceRules;
import net.minecraft.world.level.levelgen.carver.ConfiguredWorldCarver;
import net.minecraft.world.level.levelgen.feature.ConfiguredFeature;
import net.minecraft.world.level.levelgen.placement.PlacedFeature;
import net.minecraft.world.level.levelgen.placement.PlacementModifier;
import net.minecraft.world.level.levelgen.structure.Structure;
import net.minecraft.world.level.levelgen.structure.StructureSet;
import org.squinchmods.investigate.ProbeExecution;
import org.squinchmods.investigate.ProbePack;
import org.squinchmods.investigate.ProbePhase;
import org.squinchmods.investigate.ProbeRegistry;
import org.squinchmods.investigate.ProbeRequest;
import org.squinchmods.investigate.ProbeResult;
import org.squinchmods.investigate.TerminalState;
import etcodehome.freeterraforged.world.worldgen.runtime.TerraForgedChunkGenerator;

/** Censuses final worldgen mechanisms and codec round-trip coverage without mod-specific access. */
public final class WorldgenNormalizationCensusProbePack implements ProbePack {
    @Override
    public void register() {
        ProbeRegistry.register("squinch:ftf-worldgen-normalization-census", "1", Census::new);
    }

    private static final class Census implements ProbeExecution {
        private Census(ProbeRequest request) {
        }

        @Override
        public ProbeResult tick(MinecraftServer server) {
            ServerLevel level = server.overworld();
            ChunkGenerator generator = level.getChunkSource().getGenerator();
            BiomeSource biomeSource = generator.getBiomeSource();
            BiomeSource acquisitionBiomeSource = generator instanceof TerraForgedChunkGenerator terraForged
                ? terraForged.acquisitionBiomeSource()
                : biomeSource;
            RegistryOps<JsonElement> ops = RegistryOps.create(JsonOps.INSTANCE, level.registryAccess());

            Map<String, Biome> biomes = new TreeMap<>();
            Map<String, PlacedFeature> placed = new TreeMap<>();
            Map<String, ConfiguredFeature<?, ?>> configured = new TreeMap<>();
            Map<String, ConfiguredWorldCarver<?>> carvers = new TreeMap<>();
            Map<String, StructureSet> structureSets = new TreeMap<>();
            Map<String, Structure> structures = new TreeMap<>();
            Map<String, DensityFunction> densities = new TreeMap<>();
            Map<String, Integer> featureTypes = new TreeMap<>();
            Map<String, Integer> placementTypes = new TreeMap<>();
            Map<String, Integer> carverTypes = new TreeMap<>();
            Map<String, Integer> structureTypes = new TreeMap<>();
            Map<String, Integer> structurePlacementTypes = new TreeMap<>();
            Set<PlacedFeature> seenPlaced = java.util.Collections.newSetFromMap(new IdentityHashMap<>());
            Set<ConfiguredFeature<?, ?>> seenConfigured = java.util.Collections.newSetFromMap(new IdentityHashMap<>());
            Set<ConfiguredWorldCarver<?>> seenCarvers = java.util.Collections.newSetFromMap(new IdentityHashMap<>());

            Registry<Biome> biomeRegistry = level.registryAccess().registryOrThrow(Registries.BIOME);
            Registry<PlacedFeature> placedRegistry = level.registryAccess().registryOrThrow(Registries.PLACED_FEATURE);
            Registry<ConfiguredFeature<?, ?>> configuredRegistry = level.registryAccess().registryOrThrow(Registries.CONFIGURED_FEATURE);
            Registry<ConfiguredWorldCarver<?>> carverRegistry = level.registryAccess().registryOrThrow(Registries.CONFIGURED_CARVER);
            Registry<StructureSet> structureSetRegistry = level.registryAccess().registryOrThrow(Registries.STRUCTURE_SET);
            Registry<Structure> structureRegistry = level.registryAccess().registryOrThrow(Registries.STRUCTURE);
            Registry<DensityFunction> densityRegistry = level.registryAccess().registryOrThrow(Registries.DENSITY_FUNCTION);

            biomeSource.possibleBiomes().stream()
                .sorted(Comparator.comparing(holder -> holderId(holder, biomeRegistry)))
                .forEach(holder -> {
                    String biomeId = holderId(holder, biomeRegistry);
                    biomes.put(biomeId, holder.value());
                    BiomeGenerationSettings settings = generator.getBiomeGenerationSettings(holder);
                    for (GenerationStep.Carving step : GenerationStep.Carving.values()) {
                        for (Holder<ConfiguredWorldCarver<?>> carverHolder : settings.getCarvers(step)) {
                            ConfiguredWorldCarver<?> carver = carverHolder.value();
                            if (seenCarvers.add(carver)) {
                                String id = holderId(carverHolder, carverRegistry);
                                carvers.put(id, carver);
                                increment(carverTypes, key(BuiltInRegistries.CARVER.getKey(carver.worldCarver())));
                            }
                        }
                    }
                    List<HolderSet<PlacedFeature>> steps = settings.features();
                    for (HolderSet<PlacedFeature> step : steps) {
                        for (Holder<PlacedFeature> placedHolder : step) {
                            PlacedFeature placedFeature = placedHolder.value();
                            if (seenPlaced.add(placedFeature)) {
                                String id = holderId(placedHolder, placedRegistry);
                                placed.put(id, placedFeature);
                                for (PlacementModifier modifier : placedFeature.placement()) {
                                    increment(placementTypes, key(BuiltInRegistries.PLACEMENT_MODIFIER_TYPE.getKey(modifier.type())));
                                }
                            }
                            placedFeature.getFeatures().forEach(feature -> {
                                if (seenConfigured.add(feature)) {
                                    String id = registryId(configuredRegistry, feature, "[direct-configured-");
                                    configured.put(id, feature);
                                    increment(featureTypes, key(BuiltInRegistries.FEATURE.getKey(feature.feature())));
                                }
                            });
                        }
                    }
                });

            level.getChunkSource().getGeneratorState().possibleStructureSets().stream()
                .sorted(Comparator.comparing(holder -> holderId(holder, structureSetRegistry)))
                .forEach(holder -> {
                    StructureSet set = holder.value();
                    structureSets.put(holderId(holder, structureSetRegistry), set);
                    increment(structurePlacementTypes, key(BuiltInRegistries.STRUCTURE_PLACEMENT.getKey(set.placement().type())));
                    for (StructureSet.StructureSelectionEntry entry : set.structures()) {
                        Structure structure = entry.structure().value();
                        structures.put(holderId(entry.structure(), structureRegistry), structure);
                        increment(structureTypes, key(BuiltInRegistries.STRUCTURE_TYPE.getKey(structure.type())));
                    }
                });

            densityRegistry.holders()
                .sorted(Comparator.comparing(holder -> holder.key().location().toString()))
                .forEach(holder -> densities.put(holder.key().location().toString(), holder.value()));

            JsonObject data = new JsonObject();
            data.addProperty("authority", "final-frozen-overworld-worldgen-graph");
            data.addProperty("generator_class", generator.getClass().getName());
            data.addProperty("biome_source_class", biomeSource.getClass().getName());
            data.addProperty("possible_biomes", biomes.size());
            data.addProperty("active_placed_features", placed.size());
            data.addProperty("active_configured_features", configured.size());
            data.addProperty("active_configured_carvers", carvers.size());
            data.addProperty("possible_structure_sets", structureSets.size());
            data.addProperty("possible_structures", structures.size());
            data.addProperty("registered_density_functions", densities.size());
            if (generator instanceof TerraForgedChunkGenerator terraForged) {
                terraForged.plan().ifPresent(plan -> {
                    data.add("plan_diagnostics", plan.diagnostics().toJson());
                    JsonArray chunkLocalFeatures = new JsonArray();
                    plan.placedFeatures().chunkLocalClassifications().values().stream()
                        .filter(classification -> classification.eligible())
                        .map(classification -> classification.confinement().featureId().toString())
                        .sorted()
                        .forEach(chunkLocalFeatures::add);
                    data.add("chunk_local_placement_features", chunkLocalFeatures);
                });
            }
            data.add("feature_types", counts(featureTypes));
            data.add("placement_modifier_types", counts(placementTypes));
            data.add("carver_types", counts(carverTypes));
            data.add("structure_types", counts(structureTypes));
            data.add("structure_placement_types", counts(structurePlacementTypes));
            JsonObject registeredTypes = new JsonObject();
            registeredTypes.add("biome_source", keys(BuiltInRegistries.BIOME_SOURCE));
            registeredTypes.add("chunk_generator", keys(BuiltInRegistries.CHUNK_GENERATOR));
            registeredTypes.add("density_function", keys(BuiltInRegistries.DENSITY_FUNCTION_TYPE));
            registeredTypes.add("surface_rule", keys(BuiltInRegistries.MATERIAL_RULE));
            registeredTypes.add("surface_condition", keys(BuiltInRegistries.MATERIAL_CONDITION));
            registeredTypes.add("carver", keys(BuiltInRegistries.CARVER));
            registeredTypes.add("feature", keys(BuiltInRegistries.FEATURE));
            registeredTypes.add("placement_modifier", keys(BuiltInRegistries.PLACEMENT_MODIFIER_TYPE));
            registeredTypes.add("structure", keys(BuiltInRegistries.STRUCTURE_TYPE));
            registeredTypes.add("structure_placement", keys(BuiltInRegistries.STRUCTURE_PLACEMENT));
            data.add("registered_worldgen_types", registeredTypes);

            Map<String, Set<String>> knownReferences = new LinkedHashMap<>();
            knownReferences.put("biome", registryKeys(biomeRegistry));
            knownReferences.put("configured_carver", registryKeys(carverRegistry));
            knownReferences.put("configured_feature", registryKeys(configuredRegistry));
            knownReferences.put("density_function", registryKeys(densityRegistry));
            knownReferences.put("noise", registryKeys(level.registryAccess().registryOrThrow(Registries.NOISE)));
            knownReferences.put("noise_settings", registryKeys(level.registryAccess().registryOrThrow(Registries.NOISE_SETTINGS)));
            knownReferences.put("placed_feature", registryKeys(placedRegistry));
            knownReferences.put("structure", registryKeys(structureRegistry));
            knownReferences.put("structure_set", registryKeys(structureSetRegistry));
            knownReferences.put("processor_list", registryKeys(level.registryAccess().registryOrThrow(Registries.PROCESSOR_LIST)));
            knownReferences.put("template_pool", registryKeys(level.registryAccess().registryOrThrow(Registries.TEMPLATE_POOL)));

            JsonObject references = new JsonObject();
            references.add("chunk_generator", references(Map.of("active", generator), ChunkGenerator.CODEC, ops, knownReferences));
            references.add("biome_source", references(
                Map.of("acquisition", acquisitionBiomeSource), BiomeSource.CODEC, ops, knownReferences
            ));
            references.add("biomes", references(biomes, Biome.DIRECT_CODEC, ops, knownReferences));
            references.add("placed_features", references(placed, PlacedFeature.DIRECT_CODEC, ops, knownReferences));
            references.add("configured_features", references(configured, ConfiguredFeature.DIRECT_CODEC, ops, knownReferences));
            references.add("configured_carvers", references(carvers, ConfiguredWorldCarver.DIRECT_CODEC, ops, knownReferences));
            references.add("structure_sets", references(structureSets, StructureSet.DIRECT_CODEC, ops, knownReferences));
            references.add("structures", references(structures, Structure.DIRECT_CODEC, ops, knownReferences));
            references.add("density_functions", references(densities, DensityFunction.DIRECT_CODEC, ops, knownReferences));
            data.add("declarative_reference_candidates", references);

            JsonObject codec = new JsonObject();
            codec.add("chunk_generator", roundTrip(Map.of("active", generator), ChunkGenerator.CODEC, ops));
            codec.add("biome_source", roundTrip(
                Map.of("acquisition", acquisitionBiomeSource), BiomeSource.CODEC, ops
            ));
            codec.add("biomes", roundTrip(biomes, Biome.DIRECT_CODEC, ops));
            codec.add("placed_features", roundTrip(placed, PlacedFeature.DIRECT_CODEC, ops));
            codec.add("configured_features", roundTrip(configured, ConfiguredFeature.DIRECT_CODEC, ops));
            codec.add("configured_carvers", roundTrip(carvers, ConfiguredWorldCarver.DIRECT_CODEC, ops));
            codec.add("structure_sets", roundTrip(structureSets, StructureSet.DIRECT_CODEC, ops));
            codec.add("structures", roundTrip(structures, Structure.DIRECT_CODEC, ops));
            codec.add("density_functions", roundTrip(densities, DensityFunction.DIRECT_CODEC, ops));
            if (generator instanceof NoiseBasedChunkGenerator noiseGenerator) {
                NoiseGeneratorSettings settings = noiseGenerator.generatorSettings().value();
                codec.add("noise_generator_settings", roundTrip(Map.of("active", settings), NoiseGeneratorSettings.DIRECT_CODEC, ops));
                codec.add("noise_router", roundTrip(Map.of("active", settings.noiseRouter()), NoiseRouter.CODEC, ops));
                codec.add("surface_rule", roundTrip(Map.of("active", settings.surfaceRule()), SurfaceRules.RuleSource.CODEC, ops));
                references.add("noise_generator_settings", references(Map.of("active", settings), NoiseGeneratorSettings.DIRECT_CODEC, ops, knownReferences));
                references.add("noise_router", references(Map.of("active", settings.noiseRouter()), NoiseRouter.CODEC, ops, knownReferences));
                references.add("surface_rule", references(Map.of("active", settings.surfaceRule()), SurfaceRules.RuleSource.CODEC, ops, knownReferences));
            }
            data.add("codec_round_trip", codec);

            int total = 0;
            int failures = 0;
            int mismatches = 0;
            for (Map.Entry<String, JsonElement> entry : codec.entrySet()) {
                JsonObject result = entry.getValue().getAsJsonObject();
                total += result.get("objects").getAsInt();
                failures += result.get("encode_failures").getAsInt();
                failures += result.get("decode_failures").getAsInt();
                failures += result.get("reencode_failures").getAsInt();
                mismatches += result.get("non_exact_round_trips").getAsInt();
            }
            data.addProperty("codec_objects_tested", total);
            data.addProperty("codec_operation_failures", failures);
            data.addProperty("codec_json_mismatches", mismatches);
            data.add("worldgen_resource_layers", resourceLayers(server));
            ChunkGenerator clonedGenerator = cloneValue(generator, ChunkGenerator.CODEC, ops);
            data.add("generator_clone_parity", generatorCloneParity(
                generator,
                clonedGenerator,
                level.getChunkSource().randomState(),
                level,
                biomeRegistry
            ));
            return ProbeResult.complete(TerminalState.PASS, ProbePhase.GENERATION, data, total);
        }
    }

    private static <T> T cloneValue(T value, Codec<T> codec, RegistryOps<JsonElement> ops) {
        return codec.encodeStart(ops, value).flatMap(json -> codec.parse(ops, json)).result().orElse(null);
    }

    private static JsonObject resourceLayers(MinecraftServer server) {
        Map<ResourceLocation, List<Resource>> stacks = server.getResourceManager().listResourceStacks(
            "worldgen", location -> location.getPath().endsWith(".json")
        );
        Map<String, Integer> keysByCategory = new TreeMap<>();
        Map<String, Integer> layersByCategory = new TreeMap<>();
        Map<String, Integer> keysByPack = new TreeMap<>();
        Map<String, Integer> layersByPack = new TreeMap<>();
        List<String> errors = new ArrayList<>();
        JsonArray overrides = new JsonArray();
        int totalLayers = 0;
        int overriddenKeys = 0;
        List<ResourceLocation> ordered = stacks.keySet().stream().sorted().toList();
        for (ResourceLocation key : ordered) {
            List<Resource> resources = stacks.get(key);
            String category = worldgenCategory(key);
            increment(keysByCategory, category);
            layersByCategory.merge(category, resources.size(), Integer::sum);
            totalLayers += resources.size();
            Set<String> packsForKey = new LinkedHashSet<>();
            for (Resource resource : resources) {
                String pack = resource.sourcePackId();
                layersByPack.merge(pack, 1, Integer::sum);
                packsForKey.add(pack);
            }
            packsForKey.forEach(pack -> keysByPack.merge(pack, 1, Integer::sum));
            if (resources.size() > 1) {
                overriddenKeys++;
                if (overrides.size() < 64) {
                    JsonObject entry = new JsonObject();
                    entry.addProperty("key", key.toString());
                    entry.addProperty("category", category);
                    JsonArray layers = new JsonArray();
                    for (Resource resource : resources) {
                        JsonObject layer = new JsonObject();
                        layer.addProperty("pack", resource.sourcePackId());
                        try (InputStream stream = resource.open()) {
                            byte[] bytes = stream.readAllBytes();
                            layer.addProperty("bytes", bytes.length);
                            layer.addProperty("sha256", sha256(bytes));
                        } catch (IOException error) {
                            errors.add(key + " @ " + resource.sourcePackId() + " | " + error);
                        }
                        layers.add(layer);
                    }
                    entry.add("layers", layers);
                    overrides.add(entry);
                }
            }
        }
        JsonObject result = new JsonObject();
        result.addProperty("keys", stacks.size());
        result.addProperty("layers", totalLayers);
        result.addProperty("overridden_keys", overriddenKeys);
        result.add("keys_by_category", counts(keysByCategory));
        result.add("layers_by_category", counts(layersByCategory));
        result.add("keys_by_pack", counts(keysByPack));
        result.add("layers_by_pack", counts(layersByPack));
        result.add("override_examples", overrides);
        result.add("errors", strings(errors.stream().limit(32).toList()));
        return result;
    }

    private static String worldgenCategory(ResourceLocation key) {
        String path = key.getPath();
        int start = path.startsWith("worldgen/") ? "worldgen/".length() : 0;
        int end = path.indexOf('/', start);
        return end < 0 ? path.substring(start) : path.substring(start, end);
    }

    private static String sha256(byte[] value) {
        try {
            return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(value));
        } catch (NoSuchAlgorithmException error) {
            throw new IllegalStateException("SHA-256 is unavailable", error);
        }
    }

    private static JsonObject generatorCloneParity(
        ChunkGenerator original,
        ChunkGenerator clone,
        net.minecraft.world.level.levelgen.RandomState originalState,
        ServerLevel level,
        Registry<Biome> biomeRegistry
    ) {
        JsonObject result = new JsonObject();
        result.addProperty("clone_available", clone != null);
        if (clone == null) {
            return result;
        }
        result.addProperty("generator_class_equal", original.getClass().equals(clone.getClass()));
        result.addProperty("biome_source_class_equal", original.getBiomeSource().getClass().equals(clone.getBiomeSource().getClass()));
        Set<String> originalBiomes = new java.util.TreeSet<>();
        Set<String> clonedBiomes = new java.util.TreeSet<>();
        original.getBiomeSource().possibleBiomes().forEach(holder -> originalBiomes.add(holderId(holder, biomeRegistry)));
        clone.getBiomeSource().possibleBiomes().forEach(holder -> clonedBiomes.add(holderId(holder, biomeRegistry)));
        result.addProperty("possible_biomes_equal", originalBiomes.equals(clonedBiomes));

        net.minecraft.world.level.levelgen.RandomState clonedState = null;
        Climate.Sampler clonedSampler = originalState.sampler();
        if (original instanceof NoiseBasedChunkGenerator && clone instanceof NoiseBasedChunkGenerator clonedNoise) {
            try {
                Registry<net.minecraft.world.level.levelgen.synth.NormalNoise.NoiseParameters> noiseRegistry =
                    level.registryAccess().registryOrThrow(Registries.NOISE);
                clonedState = net.minecraft.world.level.levelgen.RandomState.create(
                    clonedNoise.generatorSettings().value(), noiseRegistry.asLookup(), level.getSeed()
                );
                clonedSampler = clonedState.sampler();
                result.addProperty("isolated_random_state_clone_available", true);
            } catch (RuntimeException | LinkageError error) {
                result.addProperty("isolated_random_state_clone_error", error.getClass().getName() + ": " + error.getMessage());
            }
        }

        int biomeSamples = 0;
        int biomeMismatches = 0;
        List<String> biomeExamples = new ArrayList<>();
        try {
            for (int quartX = -64; quartX <= 64; quartX += 8) {
                for (int quartZ = -64; quartZ <= 64; quartZ += 8) {
                    for (int quartY : new int[] {-16, 16, 48}) {
                        biomeSamples++;
                        Holder<Biome> first = original.getBiomeSource().getNoiseBiome(quartX, quartY, quartZ, originalState.sampler());
                        Holder<Biome> second = clone.getBiomeSource().getNoiseBiome(quartX, quartY, quartZ, clonedSampler);
                        String firstId = holderId(first, biomeRegistry);
                        String secondId = holderId(second, biomeRegistry);
                        if (!firstId.equals(secondId)) {
                            biomeMismatches++;
                            if (biomeExamples.size() < 32) {
                                biomeExamples.add(quartX + "," + quartY + "," + quartZ + " | " + firstId + " != " + secondId);
                            }
                        }
                    }
                }
            }
        } catch (RuntimeException | LinkageError error) {
            result.addProperty("biome_query_error", error.getClass().getName() + ": " + error.getMessage());
        }
        result.addProperty("biome_samples", biomeSamples);
        result.addProperty("biome_mismatches", biomeMismatches);
        result.add("biome_mismatch_examples", strings(biomeExamples));

        if (original instanceof NoiseBasedChunkGenerator && clone instanceof NoiseBasedChunkGenerator && clonedState != null) {
            try {
                Map<String, DensityFunction> originalRouter = routerFunctions(originalState.router());
                Map<String, DensityFunction> clonedRouter = routerFunctions(clonedState.router());
                int densitySamples = 0;
                int densityMismatches = 0;
                List<String> densityExamples = new ArrayList<>();
                for (String name : originalRouter.keySet()) {
                    DensityFunction first = originalRouter.get(name);
                    DensityFunction second = clonedRouter.get(name);
                    for (int x : new int[] {-128, -32, 64, 160}) {
                        for (int z : new int[] {-128, -32, 64, 160}) {
                            for (int y : new int[] {-32, 32, 96, 192}) {
                                densitySamples++;
                                DensityFunction.SinglePointContext point = new DensityFunction.SinglePointContext(x, y, z);
                                double firstValue = first.compute(point);
                                double secondValue = second.compute(point);
                                if (Double.doubleToLongBits(firstValue) != Double.doubleToLongBits(secondValue)) {
                                    densityMismatches++;
                                    if (densityExamples.size() < 32) {
                                        densityExamples.add(name + "@" + x + "," + y + "," + z + " | " + firstValue + " != " + secondValue);
                                    }
                                }
                            }
                        }
                    }
                }
                result.addProperty("density_samples", densitySamples);
                result.addProperty("density_mismatches", densityMismatches);
                result.add("density_mismatch_examples", strings(densityExamples));
            } catch (RuntimeException | LinkageError error) {
                result.addProperty("density_query_error", error.getClass().getName() + ": " + error.getMessage());
            }
        } else {
            result.addProperty("density_query_unavailable", "generator is not noise-based on both sides");
        }
        return result;
    }

    private static Map<String, DensityFunction> routerFunctions(NoiseRouter router) {
        Map<String, DensityFunction> result = new LinkedHashMap<>();
        result.put("barrier", router.barrierNoise());
        result.put("fluid_floodedness", router.fluidLevelFloodednessNoise());
        result.put("fluid_spread", router.fluidLevelSpreadNoise());
        result.put("lava", router.lavaNoise());
        result.put("temperature", router.temperature());
        result.put("vegetation", router.vegetation());
        result.put("continents", router.continents());
        result.put("erosion", router.erosion());
        result.put("depth", router.depth());
        result.put("ridges", router.ridges());
        result.put("initial_density", router.initialDensityWithoutJaggedness());
        result.put("final_density", router.finalDensity());
        result.put("vein_toggle", router.veinToggle());
        result.put("vein_ridged", router.veinRidged());
        result.put("vein_gap", router.veinGap());
        return result;
    }

    private static JsonArray strings(List<String> values) {
        JsonArray result = new JsonArray();
        values.forEach(result::add);
        return result;
    }

    private static <T> JsonObject roundTrip(Map<String, ? extends T> values, Codec<T> codec, RegistryOps<JsonElement> ops) {
        int encodedCount = 0;
        int decodedCount = 0;
        int exactRoundTrips = 0;
        int canonicalFixedPoints = 0;
        long encodedCharacters = 0;
        Map<String, Integer> typeTokens = new TreeMap<>();
        List<String> encodeFailures = new ArrayList<>();
        List<String> decodeFailures = new ArrayList<>();
        List<String> reencodeFailures = new ArrayList<>();
        List<String> nonExactRoundTrips = new ArrayList<>();
        for (Map.Entry<String, ? extends T> entry : values.entrySet()) {
            DataResult<JsonElement> encoded = codec.encodeStart(ops, entry.getValue());
            JsonElement json = encoded.result().orElse(null);
            if (json == null) {
                encodeFailures.add(entry.getKey() + " | " + error(encoded));
                continue;
            }
            encodedCount++;
            encodedCharacters += json.toString().length();
            collectTypeTokens(json, typeTokens);
            DataResult<T> decoded = codec.parse(ops, json);
            T decodedValue = decoded.result().orElse(null);
            if (decodedValue == null) {
                decodeFailures.add(entry.getKey() + " | " + error(decoded));
                continue;
            }
            decodedCount++;
            DataResult<JsonElement> reencoded = codec.encodeStart(ops, decodedValue);
            JsonElement second = reencoded.result().orElse(null);
            if (second == null) {
                reencodeFailures.add(entry.getKey() + " | " + error(reencoded));
            } else if (json.equals(second)) {
                exactRoundTrips++;
                canonicalFixedPoints++;
            } else {
                DataResult<T> canonicalDecoded = codec.parse(ops, second);
                T canonicalValue = canonicalDecoded.result().orElse(null);
                JsonElement third = canonicalValue == null ? null : codec.encodeStart(ops, canonicalValue).result().orElse(null);
                if (second.equals(third)) {
                    canonicalFixedPoints++;
                }
                nonExactRoundTrips.add(entry.getKey() + " | first=" + bounded(json) + " | canonical=" + bounded(second));
            }
        }
        JsonObject result = new JsonObject();
        result.addProperty("objects", values.size());
        result.addProperty("encoded", encodedCount);
        result.addProperty("decoded", decodedCount);
        result.addProperty("exact_json_round_trips", exactRoundTrips);
        result.addProperty("canonical_fixed_point_round_trips", canonicalFixedPoints);
        result.addProperty("encoded_characters", encodedCharacters);
        result.addProperty("encode_failures", encodeFailures.size());
        result.addProperty("decode_failures", decodeFailures.size());
        result.addProperty("reencode_failures", reencodeFailures.size());
        result.addProperty("non_exact_round_trips", nonExactRoundTrips.size());
        result.add("encoded_type_tokens", counts(typeTokens));
        result.add("failure_examples", failures(encodeFailures, decodeFailures, reencodeFailures, nonExactRoundTrips));
        return result;
    }

    private static String bounded(JsonElement value) {
        String text = value.toString();
        return text.length() <= 2048 ? text : text.substring(0, 2048) + "...";
    }

    private static <T> JsonArray keys(Registry<T> registry) {
        JsonArray result = new JsonArray();
        registry.keySet().stream().map(ResourceLocation::toString).sorted().forEach(result::add);
        return result;
    }

    private static <T> Set<String> registryKeys(Registry<T> registry) {
        Set<String> result = new LinkedHashSet<>();
        registry.keySet().stream().map(ResourceLocation::toString).sorted().forEach(result::add);
        return result;
    }

    private static <T> JsonObject references(
        Map<String, ? extends T> values,
        Codec<T> codec,
        RegistryOps<JsonElement> ops,
        Map<String, Set<String>> known
    ) {
        Map<String, Map<String, Integer>> occurrences = new TreeMap<>();
        Map<String, Set<String>> unique = new TreeMap<>();
        Set<String> tags = new java.util.TreeSet<>();
        for (T value : values.values()) {
            codec.encodeStart(ops, value).result().ifPresent(json -> collectReferences(json, null, known, occurrences, unique, tags));
        }
        JsonObject result = new JsonObject();
        for (String domain : known.keySet()) {
            Map<String, Integer> domainOccurrences = occurrences.getOrDefault(domain, Map.of());
            Set<String> domainUnique = unique.getOrDefault(domain, Set.of());
            JsonObject summary = new JsonObject();
            summary.addProperty("occurrences", domainOccurrences.values().stream().mapToInt(Integer::intValue).sum());
            summary.addProperty("unique", domainUnique.size());
            JsonArray examples = new JsonArray();
            domainUnique.stream().limit(32).forEach(examples::add);
            summary.add("examples", examples);
            result.add(domain, summary);
        }
        JsonArray tagExamples = new JsonArray();
        tags.stream().limit(32).forEach(tagExamples::add);
        result.addProperty("tag_tokens", tags.size());
        result.add("tag_examples", tagExamples);
        return result;
    }

    private static void collectReferences(
        JsonElement element,
        String field,
        Map<String, Set<String>> known,
        Map<String, Map<String, Integer>> occurrences,
        Map<String, Set<String>> unique,
        Set<String> tags
    ) {
        if (element.isJsonArray()) {
            element.getAsJsonArray().forEach(value -> collectReferences(value, field, known, occurrences, unique, tags));
        } else if (element.isJsonObject()) {
            element.getAsJsonObject().entrySet().forEach(entry ->
                collectReferences(entry.getValue(), entry.getKey(), known, occurrences, unique, tags));
        } else if (element.isJsonPrimitive() && element.getAsJsonPrimitive().isString()) {
            String value = element.getAsString();
            if (value.startsWith("#")) {
                tags.add(value);
            }
            if ("type".equals(field)) {
                return;
            }
            for (Map.Entry<String, Set<String>> entry : known.entrySet()) {
                if (entry.getValue().contains(value)) {
                    occurrences.computeIfAbsent(entry.getKey(), ignored -> new HashMap<>()).merge(value, 1, Integer::sum);
                    unique.computeIfAbsent(entry.getKey(), ignored -> new java.util.TreeSet<>()).add(value);
                }
            }
        }
    }

    private static JsonArray failures(List<String>... groups) {
        JsonArray result = new JsonArray();
        for (List<String> group : groups) {
            for (String failure : group) {
                if (result.size() >= 32) {
                    return result;
                }
                result.add(failure);
            }
        }
        return result;
    }

    private static String error(DataResult<?> result) {
        return result.error().map(problem -> problem.message()).orElse("no result and no error");
    }

    private static void collectTypeTokens(JsonElement element, Map<String, Integer> counts) {
        if (element.isJsonArray()) {
            element.getAsJsonArray().forEach(value -> collectTypeTokens(value, counts));
        } else if (element.isJsonObject()) {
            for (Map.Entry<String, JsonElement> entry : element.getAsJsonObject().entrySet()) {
                if ("type".equals(entry.getKey()) && entry.getValue().isJsonPrimitive()
                    && entry.getValue().getAsJsonPrimitive().isString()) {
                    increment(counts, entry.getValue().getAsString());
                }
                collectTypeTokens(entry.getValue(), counts);
            }
        }
    }

    private static JsonObject counts(Map<String, Integer> values) {
        JsonObject result = new JsonObject();
        values.forEach(result::addProperty);
        return result;
    }

    private static void increment(Map<String, Integer> values, String key) {
        values.merge(key, 1, Integer::sum);
    }

    private static String key(ResourceLocation key) {
        return key == null ? "[unregistered]" : key.toString();
    }

    private static <T> String holderId(Holder<T> holder, Registry<T> registry) {
        return holder.unwrapKey().map(value -> value.location().toString())
            .orElseGet(() -> registryId(registry, holder.value(), "[direct-"));
    }

    private static <T> String registryId(Registry<T> registry, T value, String directPrefix) {
        ResourceLocation id = registry.getKey(value);
        return id == null ? directPrefix + Integer.toUnsignedString(System.identityHashCode(value)) + "]" : id.toString();
    }
}
