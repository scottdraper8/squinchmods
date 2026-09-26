package org.squinchmods.investigate.ftf;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

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
import org.squinchmods.investigate.ftf.mixin.AccessorMultiNoiseBiomeSource;
import etcodehome.freeterraforged.world.worldgen.biome.UndergroundBiomeBanding;

public final class FtfReachabilityCensusProbePack implements ProbePack {
    @Override
    public void register() {
        ProbeRegistry.register("squinch:ftf-reachability-census", "1", ReachabilityCensus::new);
    }

    private static final Climate.Parameter FULL_RANGE = Climate.Parameter.span(-1.0F, 1.0F);
    private static final Climate.Parameter UNDERGROUND_DEPTH = Climate.Parameter.span(0.2F, 0.9F);
    private static final Climate.Parameter BOTTOM_DEPTH = Climate.Parameter.point(1.1F);

    static boolean isUndergroundConvention(Climate.ParameterPoint point) {
        UndergroundBiomeBanding.CandidateRole role = UndergroundBiomeBanding.classify(point, false);
        return role == UndergroundBiomeBanding.CandidateRole.SHALLOW_CAVE
            || role == UndergroundBiomeBanding.CandidateRole.DEEP_CAVE;
    }

    static long fitness(Climate.ParameterPoint point, Climate.TargetPoint target) {
        return square(point.temperature().distance(target.temperature()))
            + square(point.humidity().distance(target.humidity()))
            + square(point.continentalness().distance(target.continentalness()))
            + square(point.erosion().distance(target.erosion()))
            + square(point.depth().distance(target.depth()))
            + square(point.weirdness().distance(target.weirdness()))
            + square(point.offset());
    }

    private static long square(long value) {
        return value * value;
    }

    private static final class ReachabilityCensus implements ProbeExecution {
        private final FinishedChunkSelection selection;
        private final Integer requestedMinY;
        private final Integer requestedMaxY;
        private final int horizontalQuartStep;
        private final int verticalQuartStep;
        private final int surfaceThresholdY;

        private ReachabilityCensus(ProbeRequest request) {
            JsonObject config = request.config();
            this.selection = new FinishedChunkSelection(config, "ftf-reachability-census");
            this.requestedMinY = config.has("min_y") ? config.get("min_y").getAsInt() : null;
            this.requestedMaxY = config.has("max_y") ? config.get("max_y").getAsInt() : null;
            this.horizontalQuartStep = config.has("horizontal_quart_step")
                ? config.get("horizontal_quart_step").getAsInt()
                : 1;
            this.verticalQuartStep = config.has("vertical_quart_step")
                ? config.get("vertical_quart_step").getAsInt()
                : 1;
            this.surfaceThresholdY = config.has("surface_threshold_y")
                ? config.get("surface_threshold_y").getAsInt()
                : 62;
            if (this.horizontalQuartStep < 1 || this.horizontalQuartStep > 4
                || 4 % this.horizontalQuartStep != 0
                || this.verticalQuartStep < 1 || this.verticalQuartStep > 64) {
                throw new IllegalArgumentException("quart steps are out of range");
            }
        }

        @Override
        public ProbeResult tick(net.minecraft.server.MinecraftServer server) {
            ServerLevel level = server.overworld();
            FinishedChunkSelection.Snapshot snapshot = this.selection.poll(level);
            if (snapshot == null) {
                return null;
            }

            BiomeSource biomeSource = level.getChunkSource().getGenerator().getBiomeSource();
            if (!(biomeSource instanceof MultiNoiseBiomeSource mnbs)) {
                JsonObject data = new JsonObject();
                data.addProperty("error", "BiomeSource is not MultiNoiseBiomeSource");
                return this.selection.result(snapshot, data);
            }

            List<Pair<Climate.ParameterPoint, Holder<Biome>>> rawEntries =
                ((AccessorMultiNoiseBiomeSource) (Object) mnbs).invokeParameters().values();
            List<IndexedBiome> biomes = buildIndexedRegistry(rawEntries);
            int biomeCount = biomes.size();

            int minY = Math.max(
                level.getMinBuildHeight(),
                this.requestedMinY == null ? level.getMinBuildHeight() : this.requestedMinY
            );
            int maxY = Math.min(
                level.getMaxBuildHeight() - 1,
                this.requestedMaxY == null ? level.getMaxBuildHeight() - 1 : this.requestedMaxY
            );
            if (minY > maxY) {
                throw new IllegalArgumentException(
                    "requested vertical bounds do not intersect the world"
                );
            }

            int minQuartY = QuartPos.fromBlock(minY);
            int maxQuartY = QuartPos.fromBlock(maxY);
            int surfaceQuartY = QuartPos.fromBlock(this.surfaceThresholdY);
            Climate.Sampler sampler = level.getChunkSource().randomState().sampler();

            long totalSampled = 0;
            long surfaceSampled = 0;
            long undergroundSampled = 0;
            long[] fitnessCache = new long[biomeCount];

            for (FinishedChunkSelection.ReadyChunk ready : snapshot.ready()) {
                int chunkQuartX = ready.coordinate().x() * 4;
                int chunkQuartZ = ready.coordinate().z() * 4;
                for (int lqx = 0; lqx < 4; lqx += this.horizontalQuartStep) {
                    for (int lqz = 0; lqz < 4; lqz += this.horizontalQuartStep) {
                        int quartX = chunkQuartX + lqx;
                        int quartZ = chunkQuartZ + lqz;
                        for (int quartY = minQuartY; quartY <= maxQuartY;
                             quartY += this.verticalQuartStep) {
                            totalSampled++;
                            boolean isSurface = quartY >= surfaceQuartY;
                            if (isSurface) {
                                surfaceSampled++;
                            } else {
                                undergroundSampled++;
                            }

                            String finishedBiome = MinecraftProbeHelpers.biomeId(
                                ready.chunk().getNoiseBiome(quartX, quartY, quartZ)
                            );
                            Climate.TargetPoint target = sampler.sample(quartX, quartY, quartZ);

                            int bestIdx = -1;
                            long bestFit = Long.MAX_VALUE;
                            int secondIdx = -1;
                            long secondFit = Long.MAX_VALUE;

                            for (int i = 0; i < biomeCount; i++) {
                                long fit = biomes.get(i).minFitnessAt(target);
                                fitnessCache[i] = fit;
                                if (fit < bestFit) {
                                    if (bestIdx >= 0
                                        && !biomes.get(bestIdx).biomeId
                                            .equals(biomes.get(i).biomeId)) {
                                        secondIdx = bestIdx;
                                        secondFit = bestFit;
                                    }
                                    bestIdx = i;
                                    bestFit = fit;
                                } else if (fit < secondFit
                                    && (bestIdx < 0
                                        || !biomes.get(bestIdx).biomeId
                                            .equals(biomes.get(i).biomeId))) {
                                    secondIdx = i;
                                    secondFit = fit;
                                }
                            }

                            long winMargin = secondIdx >= 0
                                ? secondFit - bestFit : Long.MAX_VALUE;

                            for (int i = 0; i < biomeCount; i++) {
                                IndexedBiome bm = biomes.get(i);

                                if (bm.biomeId.equals(finishedBiome)) {
                                    bm.finishedChunkSelections++;
                                    if (isSurface) {
                                        bm.surfaceSelections++;
                                    } else {
                                        bm.undergroundSelections++;
                                    }
                                }

                                if (i == bestIdx) {
                                    bm.fitnessWins++;
                                    if (isSurface) {
                                        bm.surfaceFitnessWins++;
                                    } else {
                                        bm.undergroundFitnessWins++;
                                    }
                                    if (winMargin != Long.MAX_VALUE) {
                                        if (winMargin < bm.winMarginMin) {
                                            bm.winMarginMin = winMargin;
                                        }
                                        if (winMargin > bm.winMarginMax) {
                                            bm.winMarginMax = winMargin;
                                        }
                                        bm.winMarginSum += winMargin;
                                    }
                                }

                                long fit = fitnessCache[i];
                                if (fit < bm.closestApproach) {
                                    bm.closestApproach = fit;
                                    bm.closestApproachIsSurface = isSurface;
                                    if (i == bestIdx) {
                                        bm.competitorAtClosest = secondIdx >= 0
                                            ? biomes.get(secondIdx).biomeId : null;
                                        bm.competitorFitnessAtClosest = secondFit;
                                    } else {
                                        bm.competitorAtClosest = bestIdx >= 0
                                            ? biomes.get(bestIdx).biomeId : null;
                                        bm.competitorFitnessAtClosest = bestFit;
                                    }
                                }
                            }
                        }
                    }
                }
            }

            return this.selection.result(snapshot, buildOutput(
                rawEntries.size(), biomes, totalSampled, surfaceSampled, undergroundSampled, minY, maxY
            ));
        }
    }

    private static List<IndexedBiome> buildIndexedRegistry(
        List<Pair<Climate.ParameterPoint, Holder<Biome>>> entries
    ) {
        Map<String, IndexedBiome> byId = new LinkedHashMap<>();
        for (Pair<Climate.ParameterPoint, Holder<Biome>> entry : entries) {
            String biomeId = MinecraftProbeHelpers.biomeId(entry.getSecond());
            IndexedBiome bm = byId.computeIfAbsent(biomeId, IndexedBiome::new);
            bm.addEntry(entry.getFirst());
        }
        return new ArrayList<>(byId.values());
    }

    private static JsonObject buildOutput(
        int rawEntryCount, List<IndexedBiome> biomes,
        long totalSampled, long surfaceSampled, long undergroundSampled,
        int minY, int maxY
    ) {
        JsonObject data = new JsonObject();
        data.addProperty("authority", "finished-chunk-reachability-census");
        data.addProperty("fitness_authority", "re-computed-vanilla-fitness");
        data.addProperty("total_registered_entries", rawEntryCount);
        data.addProperty("total_registered_biomes", biomes.size());
        data.addProperty("total_sampled", totalSampled);
        data.addProperty("surface_sampled", surfaceSampled);
        data.addProperty("underground_sampled", undergroundSampled);
        data.addProperty("min_y", minY);
        data.addProperty("max_y", maxY);

        JsonObject census = new JsonObject();
        for (IndexedBiome bm : biomes) {
            census.add(bm.biomeId, bm.toJson());
        }
        data.add("census", census);

        long reachable = 0;
        long fragile = 0;
        long fitnessWinnerOnly = 0;
        long notObserved = 0;
        long bandingExcluded = 0;
        JsonArray notObservedList = new JsonArray();
        JsonArray fitnessOnlyList = new JsonArray();
        JsonArray fragileList = new JsonArray();
        JsonArray bandingExcludedList = new JsonArray();
        for (IndexedBiome bm : biomes) {
            String classification = bm.classify();
            if (bm.finishedChunkSelections > 0) {
                if ("FRAGILE".equals(classification)) {
                    fragile++;
                    fragileList.add(bm.biomeId);
                } else {
                    reachable++;
                }
            } else if (bm.fitnessWins > 0) {
                fitnessWinnerOnly++;
                fitnessOnlyList.add(bm.biomeId);
            } else {
                if ("BANDING_EXCLUDED".equals(classification)) {
                    bandingExcluded++;
                    bandingExcludedList.add(bm.biomeId);
                } else {
                    notObserved++;
                    notObservedList.add(bm.biomeId);
                }
            }
        }
        JsonObject summary = new JsonObject();
        summary.addProperty("reachable", reachable);
        summary.addProperty("fragile", fragile);
        summary.addProperty("fitness_winner_only", fitnessWinnerOnly);
        summary.addProperty("not_observed", notObserved);
        summary.addProperty("banding_excluded", bandingExcluded);
        summary.add("not_observed_biomes", notObservedList);
        summary.add("fitness_winner_only_biomes", fitnessOnlyList);
        summary.add("fragile_biomes", fragileList);
        summary.add("banding_excluded_biomes", bandingExcludedList);
        data.add("summary", summary);

        return data;
    }

    private static final class IndexedBiome {
        private final String biomeId;
        private final String namespace;
        private final List<Climate.ParameterPoint> parameterPoints = new ArrayList<>();
        private int undergroundConventionCount;

        private long finishedChunkSelections;
        private long surfaceSelections;
        private long undergroundSelections;
        private long fitnessWins;
        private long surfaceFitnessWins;
        private long undergroundFitnessWins;
        private long closestApproach = Long.MAX_VALUE;
        private boolean closestApproachIsSurface;
        private String competitorAtClosest;
        private long competitorFitnessAtClosest = Long.MAX_VALUE;
        private long winMarginMin = Long.MAX_VALUE;
        private long winMarginMax = Long.MIN_VALUE;
        private double winMarginSum;

        private IndexedBiome(String biomeId) {
            this.biomeId = biomeId;
            int colon = biomeId.indexOf(':');
            this.namespace = colon >= 0 ? biomeId.substring(0, colon) : "minecraft";
        }

        private void addEntry(Climate.ParameterPoint point) {
            this.parameterPoints.add(point);
            if (isUndergroundConvention(point)) {
                this.undergroundConventionCount++;
            }
        }

        private long minFitnessAt(Climate.TargetPoint target) {
            long min = Long.MAX_VALUE;
            for (Climate.ParameterPoint point : this.parameterPoints) {
                min = Math.min(min, fitness(point, target));
            }
            return min;
        }

        private boolean hasSurfaceRegistrations() {
            for (Climate.ParameterPoint point : this.parameterPoints) {
                if (!isUndergroundConvention(point)) {
                    return true;
                }
            }
            return false;
        }

        private boolean hasUndergroundRegistrations() {
            for (Climate.ParameterPoint point : this.parameterPoints) {
                float depthMin = Climate.unquantizeCoord(point.depth().min());
                if (depthMin > 0.0F) {
                    return true;
                }
            }
            return false;
        }

        private String classify() {
            if (this.fitnessWins == 0 && this.finishedChunkSelections == 0) {
                if (hasUndergroundRegistrations() && this.undergroundConventionCount == 0
                    && !hasSurfaceRegistrations()) {
                    return "BANDING_EXCLUDED";
                }
                return "UNREACHABLE";
            }
            if (this.fitnessWins > 0 && this.winMarginMin < Long.MAX_VALUE) {
                double meanMargin = this.winMarginSum / this.fitnessWins;
                // ~100K quantized fitness = sqrt(100K) ≈ 316 quantized units ≈ 0.03 float
                // per axis — wins by less than one-third of a temperature band width
                if (meanMargin < 100_000.0) {
                    return "FRAGILE";
                }
            }
            return "REACHABLE";
        }

        private JsonObject toJson() {
            JsonObject result = new JsonObject();
            result.addProperty("namespace", this.namespace);
            result.addProperty("registration_count", this.parameterPoints.size());
            result.addProperty("underground_convention_count", this.undergroundConventionCount);
            result.addProperty("finished_chunk_selections", this.finishedChunkSelections);
            result.addProperty("surface_selections", this.surfaceSelections);
            result.addProperty("underground_selections", this.undergroundSelections);
            result.addProperty("fitness_wins", this.fitnessWins);
            result.addProperty("surface_fitness_wins", this.surfaceFitnessWins);
            result.addProperty("underground_fitness_wins", this.undergroundFitnessWins);

            String status;
            if (this.finishedChunkSelections > 0) {
                status = "REACHABLE";
            } else if (this.fitnessWins > 0) {
                status = "FITNESS_WINNER_NOT_IN_CHUNKS";
            } else if (this.closestApproach < Long.MAX_VALUE) {
                status = "NOT_OBSERVED";
            } else {
                status = "NO_SAMPLES";
            }
            result.addProperty("status", status);
            result.addProperty("classification", classify());

            if (this.fitnessWins > 0) {
                JsonObject margin = new JsonObject();
                if (this.winMarginMin < Long.MAX_VALUE) {
                    margin.addProperty("min", this.winMarginMin);
                    margin.addProperty("max", this.winMarginMax);
                    margin.addProperty("mean", this.winMarginSum / this.fitnessWins);
                }
                double volume = (double) this.fitnessWins;
                margin.addProperty("fitness_wins", this.fitnessWins);
                if (this.winMarginMin < Long.MAX_VALUE) {
                    margin.addProperty("strength",
                        volume * (this.winMarginSum / this.fitnessWins));
                }
                result.add("competitive_strength", margin);
            }

            if (this.closestApproach < Long.MAX_VALUE) {
                JsonObject closest = new JsonObject();
                closest.addProperty("fitness", this.closestApproach);
                closest.addProperty("is_surface", this.closestApproachIsSurface);
                if (this.competitorAtClosest != null) {
                    closest.addProperty("competitor", this.competitorAtClosest);
                    closest.addProperty("competitor_fitness", this.competitorFitnessAtClosest);
                    closest.addProperty("fitness_gap",
                        this.closestApproach - this.competitorFitnessAtClosest);
                }
                result.add("closest_approach", closest);
            }

            JsonArray registrations = new JsonArray();
            for (Climate.ParameterPoint point : this.parameterPoints) {
                JsonObject reg = new JsonObject();
                reg.add("temperature", parameterJson(point.temperature()));
                reg.add("humidity", parameterJson(point.humidity()));
                reg.add("continentalness", parameterJson(point.continentalness()));
                reg.add("erosion", parameterJson(point.erosion()));
                reg.add("depth", parameterJson(point.depth()));
                reg.add("weirdness", parameterJson(point.weirdness()));
                reg.addProperty("offset", Climate.unquantizeCoord(point.offset()));
                reg.addProperty("is_underground_convention", isUndergroundConvention(point));
                registrations.add(reg);
            }
            result.add("registrations", registrations);

            return result;
        }

        private static JsonObject parameterJson(Climate.Parameter param) {
            JsonObject result = new JsonObject();
            result.addProperty("min", Climate.unquantizeCoord(param.min()));
            result.addProperty("max", Climate.unquantizeCoord(param.max()));
            return result;
        }
    }
}
