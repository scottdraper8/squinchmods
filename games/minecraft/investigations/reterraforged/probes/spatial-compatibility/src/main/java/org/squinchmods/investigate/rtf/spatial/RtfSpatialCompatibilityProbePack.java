package org.squinchmods.investigate.rtf.spatial;

import java.io.ByteArrayOutputStream;
import java.io.DataOutputStream;
import java.io.IOException;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Base64;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeMap;
import java.util.TreeSet;
import java.util.zip.GZIPOutputStream;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;

import net.minecraft.core.Holder;
import net.minecraft.core.QuartPos;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.util.Mth;
import net.minecraft.world.level.biome.Biome;
import net.minecraft.world.level.biome.BiomeSource;
import net.minecraft.world.level.biome.Climate;
import org.squinchmods.investigate.FinishedChunkSelection;
import org.squinchmods.investigate.MinecraftProbeHelpers;
import org.squinchmods.investigate.ProbeExecution;
import org.squinchmods.investigate.ProbePack;
import org.squinchmods.investigate.ProbeRegistry;
import org.squinchmods.investigate.ProbeRequest;
import org.squinchmods.investigate.ProbeResult;
import raccoonman.reterraforged.world.worldgen.GeneratorContext;
import raccoonman.reterraforged.world.worldgen.RTFRandomState;
import raccoonman.reterraforged.world.worldgen.cell.Cell;
import raccoonman.reterraforged.world.worldgen.runtime.TerraForgedChunkGenerator;
import raccoonman.reterraforged.world.worldgen.runtime.WorldgenPlan;
import raccoonman.reterraforged.world.worldgen.runtime.WorldgenPlans;

public final class RtfSpatialCompatibilityProbePack implements ProbePack {
    @Override
    public void register() {
        ProbeRegistry.register("squinch:rtf-spatial-compatibility", "1", SpatialCompatibility::new);
    }

    private static final class SpatialCompatibility implements ProbeExecution {
        private final FinishedChunkSelection selection;
        private final int minBlockX;
        private final int maxBlockX;
        private final int minBlockZ;
        private final int maxBlockZ;
        private final int step;

        private SpatialCompatibility(ProbeRequest request) {
            JsonObject config = request.config();
            this.selection = new FinishedChunkSelection(config, "rtf-spatial-compatibility");
            this.minBlockX = integer(config, "sample_min_block_x", -2048);
            this.maxBlockX = integer(config, "sample_max_block_x", 2040);
            this.minBlockZ = integer(config, "sample_min_block_z", -2048);
            this.maxBlockZ = integer(config, "sample_max_block_z", 2040);
            this.step = integer(config, "sample_step_blocks", 8);
            if (this.step < 4 || this.step > 64 || this.minBlockX > this.maxBlockX
                || this.minBlockZ > this.maxBlockZ) {
                throw new IllegalArgumentException("invalid spatial grid bounds or step");
            }
            long width = ((long) this.maxBlockX - this.minBlockX) / this.step + 1L;
            long height = ((long) this.maxBlockZ - this.minBlockZ) / this.step + 1L;
            if (width * height > 1_100_000L) {
                throw new IllegalArgumentException("spatial grid exceeds 1,100,000 samples");
            }
        }

        @Override
        public ProbeResult tick(net.minecraft.server.MinecraftServer server) {
            ServerLevel level = server.overworld();
            FinishedChunkSelection.Snapshot snapshot = this.selection.poll(level);
            if (snapshot == null) return null;

            BiomeSource biomeSource = level.getChunkSource().getGenerator().getBiomeSource();
            RTFRandomState randomState = (RTFRandomState) (Object) level.getChunkSource().randomState();
            GeneratorContext context = randomState.generatorContext();
            if (context == null) {
                throw new IllegalStateException("FTF GeneratorContext unavailable");
            }

            if (!(level.getChunkSource().getGenerator() instanceof TerraForgedChunkGenerator generator)) {
                throw new IllegalStateException("active Overworld generator is not the FTF-owned root");
            }
            WorldgenPlan plan = generator.plan().orElseThrow(
                () -> new IllegalStateException("FTF worldgen plan unavailable")
            );
            List<WorldgenPlans.ProviderDomain> providerDomains = plan.providerSelection().providers().stream()
                .sorted(Comparator.comparingInt(WorldgenPlans.ProviderDomain::registrationOrder))
                .toList();

            Grid grid = sample(level, biomeSource, context, plan, providerDomains);
            JsonObject data = new JsonObject();
            data.addProperty("authority", "direct-biome-source-grid-with-finished-chunk-parity");
            data.addProperty("surface_y_authority", "ftf-cell-height");
            data.addProperty("provider_contract_active", !providerDomains.isEmpty());
            data.add("provider_dictionary", strings(providerDomains.stream()
                .map(domain -> domain.id().toString()).toList()));
            data.add("grid", grid.metadata());
            data.add("biome_dictionary", strings(grid.biomeDictionary));
            data.add("original_biome_dictionary", strings(grid.originalDictionary));
            data.add("component_topology", components(grid));
            data.add("transition_ownership", transitions(grid));
            data.add("provider_distribution", providerDistribution(grid));
            data.add("finished_chunk_parity", finishedParity(snapshot, level, biomeSource, context));
            data.add("raw_grid", rawGrid(grid));
            return this.selection.result(snapshot, data);
        }

        private Grid sample(
            ServerLevel level,
            BiomeSource biomeSource,
            GeneratorContext context,
            WorldgenPlan plan,
            List<WorldgenPlans.ProviderDomain> providerDomains
        ) {
            int width = (this.maxBlockX - this.minBlockX) / this.step + 1;
            int height = (this.maxBlockZ - this.minBlockZ) / this.step + 1;
            Grid grid = new Grid(width, height, this.minBlockX, this.minBlockZ, this.step);
            Climate.Sampler sampler = level.getChunkSource().randomState().sampler();
            Map<ResourceLocation, Integer> providerIds = new HashMap<>();
            for (int index = 0; index < providerDomains.size(); index++) {
                providerIds.put(providerDomains.get(index).id(), index);
            }
            Cell cell = new Cell();
            for (int z = 0; z < height; z++) {
                int blockZ = this.minBlockZ + z * this.step;
                for (int x = 0; x < width; x++) {
                    int blockX = this.minBlockX + x * this.step;
                    int index = z * width + x;
                    cell.reset();
                    context.lookup.applyCell(cell, blockX, blockZ, true, true);
                    int surfaceY = Mth.clamp(
                        context.levels.scale(cell.height),
                        level.getMinBuildHeight(),
                        level.getMaxBuildHeight() - 1
                    );
                    int quartX = QuartPos.fromBlock(blockX);
                    int quartY = QuartPos.fromBlock(surfaceY);
                    int quartZ = QuartPos.fromBlock(blockZ);
                    Climate.TargetPoint target = sampler.sample(quartX, quartY, quartZ);
                    Holder<Biome> selected = biomeSource.getNoiseBiome(quartX, quartY, quartZ, sampler);
                    String biome = MinecraftProbeHelpers.biomeId(selected);
                    int providerIndex = -1;
                    String original = biome;
                    if (!providerDomains.isEmpty()) {
                        WorldgenPlans.ProviderResult provider = plan.providerSelection()
                            .resolve(cell.biomeRegionX, cell.biomeRegionZ, target)
                            .orElseThrow();
                        providerIndex = providerIds.getOrDefault(provider.domain(), -1);
                        original = MinecraftProbeHelpers.biomeId(provider.biome());
                    }
                    grid.biome[index] = grid.biomeId(biome);
                    grid.originalBiome[index] = grid.originalId(original);
                    grid.provider[index] = providerIndex;
                    grid.ftfCell[index] = packCell(cell.biomeRegionX, cell.biomeRegionZ);
                    grid.ftfEdge[index] = cell.biomeRegionEdge;
                    grid.surfaceY[index] = surfaceY;
                }
            }
            return grid;
        }

        private static long packCell(long cellX, long cellZ) {
            if (cellX < Integer.MIN_VALUE || cellX > Integer.MAX_VALUE
                || cellZ < Integer.MIN_VALUE || cellZ > Integer.MAX_VALUE) {
                throw new IllegalStateException("FTF biome-cell coordinate exceeds exact packed range");
            }
            return (cellX << 32) ^ (cellZ & 0xffffffffL);
        }

        private static JsonObject components(Grid grid) {
            boolean[] visited = new boolean[grid.size()];
            int[] queue = new int[grid.size()];
            Map<Integer, BiomeComponents> byBiome = new TreeMap<>();
            List<Component> all = new ArrayList<>();
            for (int start = 0; start < grid.size(); start++) {
                if (visited[start]) continue;
                int biome = grid.biome[start];
                int head = 0;
                int tail = 0;
                queue[tail++] = start;
                visited[start] = true;
                int area = 0;
                int perimeter = 0;
                int minX = grid.width;
                int maxX = -1;
                int minZ = grid.height;
                int maxZ = -1;
                Set<Integer> providers = new HashSet<>();
                Set<Long> ftfCells = new HashSet<>();
                while (head < tail) {
                    int index = queue[head++];
                    int x = index % grid.width;
                    int z = index / grid.width;
                    area++;
                    minX = Math.min(minX, x);
                    maxX = Math.max(maxX, x);
                    minZ = Math.min(minZ, z);
                    maxZ = Math.max(maxZ, z);
                    providers.add(grid.provider[index]);
                    ftfCells.add(grid.ftfCell[index]);
                    perimeter += visitNeighbor(grid, visited, queue, tail, biome, x - 1, z);
                    if (x > 0 && !visited[index - 1] && grid.biome[index - 1] == biome) {
                        visited[index - 1] = true;
                        queue[tail++] = index - 1;
                    }
                    if (x + 1 < grid.width) {
                        int neighbor = index + 1;
                        if (grid.biome[neighbor] != biome) perimeter++;
                        else if (!visited[neighbor]) { visited[neighbor] = true; queue[tail++] = neighbor; }
                    } else perimeter++;
                    if (z > 0) {
                        int neighbor = index - grid.width;
                        if (grid.biome[neighbor] != biome) perimeter++;
                        else if (!visited[neighbor]) { visited[neighbor] = true; queue[tail++] = neighbor; }
                    } else perimeter++;
                    if (z + 1 < grid.height) {
                        int neighbor = index + grid.width;
                        if (grid.biome[neighbor] != biome) perimeter++;
                        else if (!visited[neighbor]) { visited[neighbor] = true; queue[tail++] = neighbor; }
                    } else perimeter++;
                }
                Component component = new Component(
                    biome, area, perimeter, minX, maxX, minZ, maxZ, providers.size(), ftfCells.size()
                );
                all.add(component);
                byBiome.computeIfAbsent(biome, ignored -> new BiomeComponents()).add(component);
            }

            all.sort(Comparator.comparingInt(Component::area).reversed());
            JsonObject output = new JsonObject();
            output.addProperty("connectivity", 4);
            output.addProperty("sample_area_blocks2", grid.step * grid.step);
            output.addProperty("component_count", all.size());
            output.add("all_components", componentAggregate(all, grid));
            JsonObject perBiome = new JsonObject();
            for (Map.Entry<Integer, BiomeComponents> entry : byBiome.entrySet()) {
                perBiome.add(grid.biomeDictionary.get(entry.getKey()), entry.getValue().json(grid));
            }
            output.add("by_biome", perBiome);
            JsonArray largest = new JsonArray();
            for (int i = 0; i < Math.min(40, all.size()); i++) {
                largest.add(all.get(i).json(grid));
            }
            output.add("largest_components", largest);
            return output;
        }

        private static int visitNeighbor(
            Grid grid, boolean[] visited, int[] queue, int tail, int biome, int x, int z
        ) {
            // The left edge is counted here; enqueueing is handled inline to keep the queue tail local.
            return x < 0 || z < 0 || x >= grid.width || z >= grid.height
                || grid.biome[z * grid.width + x] != biome ? 1 : 0;
        }

        private static JsonObject componentAggregate(List<Component> components, Grid grid) {
            List<Integer> sizes = components.stream().map(Component::area).sorted().toList();
            long samples = sizes.stream().mapToLong(Integer::longValue).sum();
            long micro4 = sizes.stream().filter(value -> value <= 4).mapToLong(Integer::longValue).sum();
            long micro16 = sizes.stream().filter(value -> value <= 16).mapToLong(Integer::longValue).sum();
            JsonObject json = new JsonObject();
            json.addProperty("component_count", sizes.size());
            json.addProperty("sample_count", samples);
            json.addProperty("mean_samples", sizes.isEmpty() ? 0.0 : samples / (double) sizes.size());
            json.addProperty("p50_samples", percentile(sizes, 0.50));
            json.addProperty("p95_samples", percentile(sizes, 0.95));
            json.addProperty("largest_samples", sizes.isEmpty() ? 0 : sizes.get(sizes.size() - 1));
            json.addProperty("area_fraction_components_le_4", samples == 0 ? 0.0 : micro4 / (double) samples);
            json.addProperty("area_fraction_components_le_16", samples == 0 ? 0.0 : micro16 / (double) samples);
            json.addProperty("sample_area_blocks2", grid.step * grid.step);
            return json;
        }

        private static JsonObject transitions(Grid grid) {
            Map<String, BoundaryStats> categories = new LinkedHashMap<>();
            categories.put("interior", new BoundaryStats());
            categories.put("provider_only", new BoundaryStats());
            categories.put("ftf_cell_only", new BoundaryStats());
            categories.put("both", new BoundaryStats());
            for (int z = 0; z < grid.height; z++) {
                for (int x = 0; x < grid.width; x++) {
                    int index = z * grid.width + x;
                    if (x + 1 < grid.width) recordBoundary(categories, grid, index, index + 1);
                    if (z + 1 < grid.height) recordBoundary(categories, grid, index, index + grid.width);
                }
            }
            JsonObject json = new JsonObject();
            for (Map.Entry<String, BoundaryStats> entry : categories.entrySet()) {
                json.add(entry.getKey(), entry.getValue().json());
            }
            return json;
        }

        private static void recordBoundary(
            Map<String, BoundaryStats> categories, Grid grid, int left, int right
        ) {
            boolean provider = grid.provider[left] != grid.provider[right];
            boolean cell = grid.ftfCell[left] != grid.ftfCell[right];
            String category = provider ? (cell ? "both" : "provider_only")
                : (cell ? "ftf_cell_only" : "interior");
            categories.get(category).add(
                grid.biome[left] != grid.biome[right],
                (grid.ftfEdge[left] + grid.ftfEdge[right]) * 0.5
            );
        }

        private static JsonObject providerDistribution(Grid grid) {
            Map<Integer, ProviderStats> providers = new TreeMap<>();
            Map<Integer, Set<Integer>> originalProviders = new TreeMap<>();
            for (int i = 0; i < grid.size(); i++) {
                providers.computeIfAbsent(grid.provider[i], ignored -> new ProviderStats())
                    .add(grid.biome[i], grid.originalBiome[i]);
                originalProviders.computeIfAbsent(grid.originalBiome[i], ignored -> new TreeSet<>())
                    .add(grid.provider[i]);
            }
            JsonObject json = new JsonObject();
            JsonObject providerJson = new JsonObject();
            for (Map.Entry<Integer, ProviderStats> entry : providers.entrySet()) {
                providerJson.add(Integer.toString(entry.getKey()), entry.getValue().json(grid));
            }
            json.add("providers", providerJson);
            JsonObject spanning = new JsonObject();
            for (Map.Entry<Integer, Set<Integer>> entry : originalProviders.entrySet()) {
                spanning.addProperty(
                    grid.originalDictionary.get(entry.getKey()), entry.getValue().size()
                );
            }
            json.add("original_biome_provider_counts", spanning);
            return json;
        }

        private static JsonObject finishedParity(
            FinishedChunkSelection.Snapshot snapshot,
            ServerLevel level,
            BiomeSource biomeSource,
            GeneratorContext context
        ) {
            Climate.Sampler sampler = level.getChunkSource().randomState().sampler();
            Cell cell = new Cell();
            long sampled = 0;
            long mismatch = 0;
            JsonArray examples = new JsonArray();
            for (FinishedChunkSelection.ReadyChunk ready : snapshot.ready()) {
                int baseQuartX = ready.coordinate().x() * 4;
                int baseQuartZ = ready.coordinate().z() * 4;
                for (int localX = 0; localX < 4; localX++) {
                    for (int localZ = 0; localZ < 4; localZ++) {
                        int quartX = baseQuartX + localX;
                        int quartZ = baseQuartZ + localZ;
                        cell.reset();
                        context.lookup.applyCell(
                            cell, QuartPos.toBlock(quartX), QuartPos.toBlock(quartZ), true, true
                        );
                        int surfaceY = Mth.clamp(context.levels.scale(cell.height),
                            level.getMinBuildHeight(), level.getMaxBuildHeight() - 1);
                        int quartY = QuartPos.fromBlock(surfaceY);
                        String stored = MinecraftProbeHelpers.biomeId(
                            ready.chunk().getNoiseBiome(quartX, quartY, quartZ)
                        );
                        String direct = MinecraftProbeHelpers.biomeId(
                            biomeSource.getNoiseBiome(quartX, quartY, quartZ, sampler)
                        );
                        sampled++;
                        if (!stored.equals(direct)) {
                            mismatch++;
                            if (examples.size() < 20) {
                                JsonObject example = new JsonObject();
                                example.addProperty("quart_x", quartX);
                                example.addProperty("quart_y", quartY);
                                example.addProperty("quart_z", quartZ);
                                example.addProperty("stored", stored);
                                example.addProperty("direct", direct);
                                examples.add(example);
                            }
                        }
                    }
                }
            }
            JsonObject json = new JsonObject();
            json.addProperty("sampled", sampled);
            json.addProperty("mismatches", mismatch);
            json.addProperty("match_fraction", sampled == 0 ? 0.0 : (sampled - mismatch) / (double) sampled);
            json.add("examples", examples);
            return json;
        }

        private static JsonObject rawGrid(Grid grid) {
            try {
                ByteArrayOutputStream bytes = new ByteArrayOutputStream();
                try (GZIPOutputStream gzip = new GZIPOutputStream(bytes);
                     DataOutputStream out = new DataOutputStream(gzip)) {
                    out.writeInt(0x52544653); // RTFS
                    out.writeInt(2);
                    out.writeInt(grid.width);
                    out.writeInt(grid.height);
                    out.writeInt(grid.originX);
                    out.writeInt(grid.originZ);
                    out.writeInt(grid.step);
                    for (int i = 0; i < grid.size(); i++) {
                        out.writeInt(grid.biome[i]);
                        out.writeInt(grid.originalBiome[i]);
                        out.writeInt(grid.provider[i]);
                        out.writeLong(grid.ftfCell[i]);
                        out.writeInt(Float.floatToRawIntBits(grid.ftfEdge[i]));
                        out.writeInt(grid.surfaceY[i]);
                    }
                }
                byte[] compressed = bytes.toByteArray();
                JsonObject json = new JsonObject();
                json.addProperty("encoding", "base64+gzip+big-endian-int32");
                json.addProperty("schema", "magic,version,width,height,origin_x,origin_z,step; then row-major biome,original_biome,provider_index,ftf_cell_packed_int64,ftf_edge_float_bits,surface_y");
                json.addProperty("compressed_bytes", compressed.length);
                json.addProperty("sha256", hex(MessageDigest.getInstance("SHA-256").digest(compressed)));
                json.addProperty("data", Base64.getEncoder().encodeToString(compressed));
                return json;
            } catch (IOException | NoSuchAlgorithmException exception) {
                throw new IllegalStateException("cannot encode spatial grid", exception);
            }
        }

        private static JsonArray strings(List<String> values) {
            JsonArray array = new JsonArray();
            values.forEach(array::add);
            return array;
        }

        private static int percentile(List<Integer> values, double percentile) {
            if (values.isEmpty()) return 0;
            return values.get((int) Math.ceil(percentile * values.size()) - 1);
        }

        private static int integer(JsonObject config, String key, int fallback) {
            return config.has(key) ? config.get(key).getAsInt() : fallback;
        }

        private static String hex(byte[] bytes) {
            StringBuilder value = new StringBuilder(bytes.length * 2);
            for (byte current : bytes) value.append(String.format("%02x", current & 0xff));
            return value.toString();
        }
    }

    private static final class Grid {
        final int width;
        final int height;
        final int originX;
        final int originZ;
        final int step;
        final int[] biome;
        final int[] originalBiome;
        final int[] provider;
        final long[] ftfCell;
        final float[] ftfEdge;
        final int[] surfaceY;
        final List<String> biomeDictionary = new ArrayList<>();
        final List<String> originalDictionary = new ArrayList<>();
        final Map<String, Integer> biomeIds = new HashMap<>();
        final Map<String, Integer> originalIds = new HashMap<>();

        Grid(int width, int height, int originX, int originZ, int step) {
            this.width = width;
            this.height = height;
            this.originX = originX;
            this.originZ = originZ;
            this.step = step;
            int size = width * height;
            this.biome = new int[size];
            this.originalBiome = new int[size];
            this.provider = new int[size];
            this.ftfCell = new long[size];
            this.ftfEdge = new float[size];
            this.surfaceY = new int[size];
        }

        int size() { return this.width * this.height; }

        int biomeId(String id) {
            return this.biomeIds.computeIfAbsent(id, key -> {
                this.biomeDictionary.add(key);
                return this.biomeDictionary.size() - 1;
            });
        }

        int originalId(String id) {
            return this.originalIds.computeIfAbsent(id, key -> {
                this.originalDictionary.add(key);
                return this.originalDictionary.size() - 1;
            });
        }

        JsonObject metadata() {
            JsonObject json = new JsonObject();
            json.addProperty("width", this.width);
            json.addProperty("height", this.height);
            json.addProperty("sample_count", this.size());
            json.addProperty("origin_block_x", this.originX);
            json.addProperty("origin_block_z", this.originZ);
            json.addProperty("step_blocks", this.step);
            json.addProperty("covered_width_blocks", (this.width - 1) * this.step);
            json.addProperty("covered_height_blocks", (this.height - 1) * this.step);
            return json;
        }
    }

    private record Component(
        int biome, int area, int perimeter, int minX, int maxX, int minZ, int maxZ,
        int providerCount, int ftfCellCount
    ) {
        JsonObject json(Grid grid) {
            JsonObject json = new JsonObject();
            json.addProperty("biome", grid.biomeDictionary.get(this.biome));
            json.addProperty("samples", this.area);
            json.addProperty("area_blocks2", (long) this.area * grid.step * grid.step);
            json.addProperty("perimeter_blocks", (long) this.perimeter * grid.step);
            json.addProperty("compactness", this.perimeter == 0 ? 0.0
                : 4.0 * Math.PI * this.area / ((double) this.perimeter * this.perimeter));
            json.addProperty("min_block_x", grid.originX + this.minX * grid.step);
            json.addProperty("max_block_x", grid.originX + this.maxX * grid.step);
            json.addProperty("min_block_z", grid.originZ + this.minZ * grid.step);
            json.addProperty("max_block_z", grid.originZ + this.maxZ * grid.step);
            json.addProperty("provider_domains", this.providerCount);
            json.addProperty("ftf_cells", this.ftfCellCount);
            return json;
        }
    }

    private static final class BiomeComponents {
        final List<Component> components = new ArrayList<>();
        void add(Component component) { this.components.add(component); }
        JsonObject json(Grid grid) {
            this.components.sort(Comparator.comparingInt(Component::area));
            JsonObject json = SpatialCompatibility.componentAggregate(this.components, grid);
            long spanningProviders = this.components.stream().filter(value -> value.providerCount > 1).count();
            long spanningCells = this.components.stream().filter(value -> value.ftfCellCount > 1).count();
            json.addProperty("components_spanning_multiple_provider_domains", spanningProviders);
            json.addProperty("components_spanning_multiple_ftf_cells", spanningCells);
            Component largest = this.components.get(this.components.size() - 1);
            json.add("largest_component", largest.json(grid));
            return json;
        }
    }

    private static final class BoundaryStats {
        long edges;
        long biomeChanges;
        double edgeSum;
        float edgeMin = Float.POSITIVE_INFINITY;
        float edgeMax = Float.NEGATIVE_INFINITY;
        void add(boolean biomeChange, double edge) {
            this.edges++;
            if (biomeChange) this.biomeChanges++;
            this.edgeSum += edge;
            this.edgeMin = Math.min(this.edgeMin, (float) edge);
            this.edgeMax = Math.max(this.edgeMax, (float) edge);
        }
        JsonObject json() {
            JsonObject json = new JsonObject();
            json.addProperty("adjacent_edges", this.edges);
            json.addProperty("biome_changes", this.biomeChanges);
            json.addProperty("biome_change_fraction", this.edges == 0 ? 0.0 : this.biomeChanges / (double) this.edges);
            json.addProperty("mean_ftf_biome_region_edge", this.edges == 0 ? 0.0 : this.edgeSum / this.edges);
            json.addProperty("min_ftf_biome_region_edge", this.edges == 0 ? 0.0 : this.edgeMin);
            json.addProperty("max_ftf_biome_region_edge", this.edges == 0 ? 0.0 : this.edgeMax);
            return json;
        }
    }

    private static final class ProviderStats {
        long samples;
        final Map<Integer, Long> selected = new TreeMap<>();
        final Map<Integer, Long> original = new TreeMap<>();
        void add(int selectedBiome, int originalBiome) {
            this.samples++;
            this.selected.merge(selectedBiome, 1L, Long::sum);
            this.original.merge(originalBiome, 1L, Long::sum);
        }
        JsonObject json(Grid grid) {
            JsonObject json = new JsonObject();
            json.addProperty("samples", this.samples);
            json.add("selected_biomes", counts(this.selected, grid.biomeDictionary));
            json.add("original_biomes", counts(this.original, grid.originalDictionary));
            return json;
        }
        private static JsonObject counts(Map<Integer, Long> counts, List<String> dictionary) {
            JsonObject json = new JsonObject();
            counts.entrySet().stream()
                .sorted(Map.Entry.<Integer, Long>comparingByValue().reversed())
                .forEach(entry -> json.addProperty(dictionary.get(entry.getKey()), entry.getValue()));
            return json;
        }
    }
}
