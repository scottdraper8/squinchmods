package org.squinchmods.investigate.rtf;

import java.util.HashMap;
import java.util.Map;
import java.util.TreeMap;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;

import net.minecraft.core.HolderLookup;
import net.minecraft.core.Holder;
import net.minecraft.core.QuartPos;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.biome.Biome;
import net.minecraft.world.level.biome.Climate;
import org.squinchmods.investigate.FinishedChunkSelection;
import org.squinchmods.investigate.MinecraftProbeHelpers;
import org.squinchmods.investigate.ProbeExecution;
import org.squinchmods.investigate.ProbePack;
import org.squinchmods.investigate.ProbePhase;
import org.squinchmods.investigate.ProbeRegistry;
import org.squinchmods.investigate.ProbeRequest;
import org.squinchmods.investigate.ProbeResult;
import org.squinchmods.investigate.TerminalState;

import raccoonman.reterraforged.data.worldgen.preset.settings.Preset;
import raccoonman.reterraforged.registries.RTFRegistries;
import raccoonman.reterraforged.world.worldgen.GeneratorContext;
import raccoonman.reterraforged.world.worldgen.RTFRandomState;
import raccoonman.reterraforged.world.worldgen.biome.BiomePreviewIntegration;
import raccoonman.reterraforged.world.worldgen.biome.BiomePreviewResolver;
import raccoonman.reterraforged.world.worldgen.cell.Cell;
import raccoonman.reterraforged.world.worldgen.densityfunction.tile.Tile;
import raccoonman.reterraforged.world.worldgen.terrablender.TerraBlenderParameterList;

/** Finished-chunk comparison for the exact resolver used by the preset previews. */
public final class RtfBiomePreviewParityProbePack implements ProbePack {
    @Override
    public void register() {
        ProbeRegistry.register("squinch:rtf-biome-preview-parity", "1", PreviewParity::new);
    }

    private static final class PreviewParity implements ProbeExecution {
        private final FinishedChunkSelection selection;
        private final int horizontalQuartStep;
        private final int exampleLimit;
        private final boolean useServerGeneratorContext;
        private final boolean useTileAuthority;
        private final boolean useFullProvider;

        private PreviewParity(ProbeRequest request) {
            JsonObject config = request.config();
            this.selection = new FinishedChunkSelection(config, "rtf-biome-preview-parity");
            this.horizontalQuartStep = config.has("horizontal_quart_step")
                ? config.get("horizontal_quart_step").getAsInt()
                : 1;
            this.exampleLimit = config.has("example_limit")
                ? config.get("example_limit").getAsInt()
                : 32;
            this.useServerGeneratorContext = config.has("use_server_generator_context")
                && config.get("use_server_generator_context").getAsBoolean();
            this.useTileAuthority = !config.has("use_tile_authority")
                || config.get("use_tile_authority").getAsBoolean();
            this.useFullProvider = !config.has("use_full_provider")
                || config.get("use_full_provider").getAsBoolean();
            if (this.horizontalQuartStep < 1 || this.horizontalQuartStep > 4
                || 4 % this.horizontalQuartStep != 0
                || this.exampleLimit < 0 || this.exampleLimit > 1024) {
                throw new IllegalArgumentException(
                    "horizontal_quart_step must divide four and example_limit must be 0..1024"
                );
            }
        }

        @Override
        public ProbeResult tick(net.minecraft.server.MinecraftServer server) {
            ServerLevel level = server.overworld();
            FinishedChunkSelection.Snapshot snapshot = this.selection.poll(level);
            if (snapshot == null) {
                return null;
            }
            if (!snapshot.complete()) {
                return this.selection.result(snapshot, new JsonObject());
            }

            Object randomState = level.getChunkSource().randomState();
            if (!(randomState instanceof RTFRandomState rtfRandomState)) {
                return ProbeResult.partial(
                    ProbePhase.FINISHED_CHUNK, new JsonObject(), 0, snapshot.requested(),
                    "overworld-random-state-is-not-rtf"
                );
            }
            Preset preset = rtfRandomState.preset();
            if (preset == null || rtfRandomState.generatorContext() == null) {
                return ProbeResult.partial(
                    ProbePhase.FINISHED_CHUNK, new JsonObject(), 0, snapshot.requested(),
                    "rtf-preset-or-generator-context-unavailable"
                );
            }

            HolderLookup.Provider previewProvider = this.useFullProvider
                ? preset.buildFullPatch(server.registryAccess())
                : preset.buildPatch(server.registryAccess());
            GeneratorContext context = this.useServerGeneratorContext
                ? rtfRandomState.generatorContext()
                : GeneratorContext.makeUncached(
                    preset,
                    previewProvider.lookupOrThrow(RTFRegistries.NOISE),
                    (int) level.getSeed(),
                    4,
                    0,
                    6
                );
            BiomePreviewResolver resolver = BiomePreviewResolver.create(
                server.registryAccess(),
                previewProvider,
                level.dimensionTypeRegistration(),
                level.getChunkSource().getGenerator(),
                preset,
                context,
                level.getSeed()
            );
            long sampled = 0;
            long mismatches = 0;
            long undergroundPreviewSelections = 0;
            Map<String, Long> biomeCounts = new TreeMap<>();
            Map<Integer, Long> terraBlenderRegionCounts = new TreeMap<>();
            long terraBlenderFallbacks = 0;
            JsonArray mismatchExamples = new JsonArray();
            Cell cell = new Cell();
            Map<Long, Tile> tiles = new HashMap<>();
            Map<Long, Climate.Sampler> tileSamplers = new HashMap<>();
            try (BiomePreviewIntegration.Session integrationSession = resolver.openIntegrationSession()) {
                for (FinishedChunkSelection.ReadyChunk ready : snapshot.ready()) {
                    int chunkQuartX = ready.coordinate().x() * 4;
                    int chunkQuartZ = ready.coordinate().z() * 4;
                    for (int localQuartX = 0; localQuartX < 4; localQuartX += this.horizontalQuartStep) {
                        for (int localQuartZ = 0; localQuartZ < 4; localQuartZ += this.horizontalQuartStep) {
                            int quartX = chunkQuartX + localQuartX;
                            int quartZ = chunkQuartZ + localQuartZ;
                            int blockX = QuartPos.toBlock(quartX) + 2;
                            int blockZ = QuartPos.toBlock(quartZ) + 2;
                            Climate.Sampler sampler = null;
                            if (this.useTileAuthority) {
                                int tileSize = context.generator.getTileBlockSize();
                                int tileX = Math.floorDiv(blockX, tileSize);
                                int tileZ = Math.floorDiv(blockZ, tileSize);
                                long tileKey = ((long) tileX << 32) ^ (tileZ & 0xFFFFFFFFL);
                                Tile tile = tiles.computeIfAbsent(tileKey,
                                    ignored -> context.generator.generate(tileX, tileZ).join());
                                sampler = tileSamplers.computeIfAbsent(tileKey,
                                    ignored -> resolver.tileClimateSamplerAtOrigin(tile, tile.getBlockX(), tile.getBlockZ(), 1));
                                cell.copyFrom(tile.lookup(blockX - tile.getBlockX(), blockZ - tile.getBlockZ()));
                            } else {
                                context.lookup.applyCell(cell.reset(), blockX, blockZ, true, false);
                            }
                            int surfaceY = clampSurfaceY(context, cell);
                            int quartY = QuartPos.fromBlock(surfaceY);

                            String stored = MinecraftProbeHelpers.biomeId(
                                ready.chunk().getNoiseBiome(quartX, quartY, quartZ)
                            );
                            Holder<Biome> previewHolder = sampler == null
                                ? resolver.resolveQuart(quartX, quartY, quartZ)
                                : resolver.resolveQuart(quartX, quartY, quartZ, sampler);
                            TerraBlenderParameterList.SelectionDiagnostics<Holder<Biome>> region =
                                sampler == null
                                    ? resolver.inspectTerraBlenderSelection(quartX, quartY, quartZ)
                                    : resolver.inspectTerraBlenderSelection(quartX, quartY, quartZ, sampler);
                            terraBlenderRegionCounts.merge(region.selectedRegion(), 1L, Long::sum);
                            if (region.usedFallback()) {
                                terraBlenderFallbacks++;
                            }
                            String preview = MinecraftProbeHelpers.biomeId(previewHolder);
                            sampled++;
                            if (resolver.isUnderground(previewHolder)) {
                                undergroundPreviewSelections++;
                            }
                            biomeCounts.merge(stored, 1L, Long::sum);
                            if (!stored.equals(preview)) {
                                mismatches++;
                                if (mismatchExamples.size() < this.exampleLimit) {
                                    mismatchExamples.add(example(blockX, surfaceY, blockZ, stored, preview));
                                }
                            }
                        }
                    }
                }
            } finally {
                tiles.values().forEach(Tile::close);
            }

            JsonObject data = new JsonObject();
            data.addProperty("authority", "preview-resolver-vs-finished-chunk-quart-palette");
            data.addProperty("query_path", "BiomeSource.getNoiseBiome(quartX,quartY,quartZ,sampler)");
            data.addProperty("surface_y_authority", this.useTileAuthority ? "prepared-preview-tile" : "rtf-preview-cell-model");
            data.addProperty("climate_sampler_authority", this.useTileAuthority ? "prepared-preview-tile" : "generator-context");
            data.addProperty("provider_authority", this.useFullProvider ? "materialized-full-provider" : "patch-provider");
            data.addProperty("active_preview_integrations", String.join(",", resolver.activeIntegrations()));
            JsonObject terraBlenderRegions = new JsonObject();
            terraBlenderRegionCounts.forEach((region, count) -> terraBlenderRegions.addProperty(String.valueOf(region), count));
            data.add("terrablender_selected_region_counts", terraBlenderRegions);
            data.addProperty("terrablender_selection_fallbacks", terraBlenderFallbacks);
            String generatorContextMode = this.useServerGeneratorContext
                ? "server-cached-context"
                : "uncached-editor-factor-4";
            data.addProperty("generator_context", generatorContextMode);
            data.addProperty("sampled_quart_columns", sampled);
            data.addProperty("mismatch_count", mismatches);
            data.addProperty("underground_preview_selection_count", undergroundPreviewSelections);
            data.addProperty("horizontal_quart_step", this.horizontalQuartStep);
            JsonObject storedBiomeCounts = new JsonObject();
            biomeCounts.forEach(storedBiomeCounts::addProperty);
            data.add("stored_biome_counts", storedBiomeCounts);
            data.add("mismatch_examples", mismatchExamples);
            return ProbeResult.complete(
                mismatches == 0 && undergroundPreviewSelections == 0 ? TerminalState.PASS : TerminalState.FAIL,
                ProbePhase.FINISHED_CHUNK,
                data,
                snapshot.ready().size()
            );
        }

        private static int clampSurfaceY(GeneratorContext context, Cell cell) {
            int minY = -context.levels.worldDepth;
            int maxY = Math.max(minY, context.levels.worldHeight - 1);
            return Math.max(minY, Math.min(maxY, context.levels.scale(cell.height)));
        }

        private static JsonObject example(
            int blockX,
            int blockY,
            int blockZ,
            String stored,
            String preview
        ) {
            JsonObject result = new JsonObject();
            result.addProperty("x", blockX);
            result.addProperty("y", blockY);
            result.addProperty("z", blockZ);
            result.addProperty("stored_biome_id", stored);
            result.addProperty("preview_biome_id", preview);
            return result;
        }
    }
}
