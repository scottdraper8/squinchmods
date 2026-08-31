package org.squinchmods.investigate.rtf;

import java.util.Comparator;
import java.util.List;
import java.util.Set;
import java.util.TreeSet;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.mojang.serialization.JsonOps;

import net.minecraft.core.Holder;
import net.minecraft.core.Registry;
import net.minecraft.core.registries.Registries;
import net.minecraft.resources.RegistryOps;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.biome.Biome;
import net.minecraft.world.level.biome.Climate;
import net.minecraft.world.level.biome.MultiNoiseBiomeSource;
import net.minecraft.world.level.dimension.LevelStem;
import net.minecraft.world.level.levelgen.DensityFunction;
import net.minecraft.world.level.levelgen.NoiseBasedChunkGenerator;
import org.squinchmods.investigate.ProbeExecution;
import org.squinchmods.investigate.ProbePack;
import org.squinchmods.investigate.ProbePhase;
import org.squinchmods.investigate.ProbeRegistry;
import org.squinchmods.investigate.ProbeRequest;
import org.squinchmods.investigate.ProbeResult;
import org.squinchmods.investigate.TerminalState;
import raccoonman.reterraforged.world.worldgen.lithostitched.LithostitchedInjectionBridge;
import raccoonman.reterraforged.world.worldgen.runtime.MinecraftWorldgenPlanCompiler;
import raccoonman.reterraforged.world.worldgen.runtime.PreviewRequest;
import raccoonman.reterraforged.world.worldgen.runtime.TagEpoch;
import raccoonman.reterraforged.world.worldgen.runtime.TerraForgedChunkGenerator;
import raccoonman.reterraforged.world.worldgen.runtime.WorldgenCapabilityDiscovery;
import raccoonman.reterraforged.world.worldgen.runtime.WorldgenCompilationPurpose;

public final class LithostitchedSnapshotProbePack implements ProbePack {
	@Override
	public void register() {
		ProbeRegistry.register("squinch:ftf-lithostitched-snapshot", "1", SnapshotProbe::new);
	}

	private static final class SnapshotProbe implements ProbeExecution {
		private SnapshotProbe(ProbeRequest request) {
		}

		@Override
		public ProbeResult tick(MinecraftServer server) {
			ServerLevel level = server.overworld();
			var source = level.getChunkSource().getGenerator().getBiomeSource();
			var found = LithostitchedInjectionBridge.snapshot(source);
			if (found.isEmpty()) {
				JsonObject data = new JsonObject();
				data.addProperty("source_class", source.getClass().getName());
				return ProbeResult.complete(TerminalState.FAIL, ProbePhase.GENERATION, data, 0);
			}

			var snapshot = found.orElseThrow();
			Registry<Biome> biomes = level.registryAccess().registryOrThrow(Registries.BIOME);
			RegistryOps<JsonElement> ops = RegistryOps.create(JsonOps.INSTANCE, level.registryAccess());
			JsonObject data = new JsonObject();
			data.addProperty("mechanism_version", snapshot.mechanismVersion());
			data.addProperty("seed", snapshot.seed());
			data.addProperty("root_class", snapshot.root().getClass().getName());
			data.addProperty("base_entry_count", snapshot.baseEntries().size());
			data.addProperty("injector_count", snapshot.injectors().size());
			data.addProperty("region_count", snapshot.regions().size());
			data.addProperty("native_region_function_present", snapshot.nativeRegionFunctionPresent());
			data.add("clone_failures", strings(snapshot.cloneFailures()));

			Set<String> possibleOutputs = new TreeSet<>();
			JsonArray injectors = new JsonArray();
			for (var injector : snapshot.injectors().stream()
				.sorted(Comparator.comparingInt(LithostitchedInjectionBridge.CapturedInjector::encounterOrder))
				.toList()) {
				JsonObject item = new JsonObject();
				item.addProperty("id", injector.id().toString());
				item.addProperty("codec", injector.codec().toString());
				item.addProperty("kind", injector.kind().name());
				item.addProperty("encounter_order", injector.encounterOrder());
				item.addProperty("priority", injector.priority());
				item.addProperty("dimension", injector.dimension().location().toString());
				injector.loadPredicateCodec().ifPresent(value -> item.addProperty(
					"load_predicate_codec", value.toString()
				));
				injector.loadPredicateResult().ifPresent(value -> item.addProperty(
					"load_predicate_accepted", value
				));
				item.add("targets", holders(injector.targets(), biomes));
				injector.output().ifPresent(holder -> {
					String id = holderId(holder, biomes);
					item.addProperty("output", id);
					possibleOutputs.add(id);
				});
				JsonArray points = new JsonArray();
				for (var point : injector.points()) {
					String id = holderId(point.getSecond(), biomes);
					points.add(id);
					possibleOutputs.add(id);
				}
				item.add("point_outputs", points);
				injector.criteria().ifPresent(criteria -> item.add("criteria", criteria(criteria, ops)));
				injectors.add(item);
			}
			data.add("injectors", injectors);
			data.add("possible_outputs", strings(possibleOutputs));

			JsonObject executionOrder = new JsonObject();
			for (var kind : LithostitchedInjectionBridge.Kind.values()) {
				List<String> ids = snapshot.injectors().stream()
					.filter(injector -> injector.kind() == kind)
					.sorted(Comparator
						.comparingInt(LithostitchedInjectionBridge.CapturedInjector::priority)
						.thenComparing(LithostitchedInjectionBridge.CapturedInjector::id))
					.map(injector -> injector.id().toString())
					.toList();
				if (!ids.isEmpty()) {
					executionOrder.add(kind.name(), strings(ids));
				}
			}
			data.add("execution_order", executionOrder);

			JsonArray regions = new JsonArray();
			for (var region : snapshot.regions()) {
				JsonObject item = new JsonObject();
				item.addProperty("id", region.id().toString());
				item.addProperty("dimension", region.dimension().location().toString());
				item.addProperty("weight", region.weight());
				item.add("biomes", holders(region.biomes(), biomes));
				regions.add(item);
			}
			data.add("regions", regions);

			if (!(level.getChunkSource().getGenerator() instanceof NoiseBasedChunkGenerator noiseGenerator)) {
				throw new IllegalStateException("active generator is not noise based");
			}
			var declarative = LithostitchedInjectionBridge.captureDeclarative(
				snapshot.root(), level.registryAccess(), LevelStem.OVERWORLD,
				noiseGenerator.generatorSettings().value(), level.getSeed()
			);
			data.addProperty("declarative_reacquisition_present", declarative.isPresent());
			data.addProperty("declarative_reacquisition_injectors", declarative.map(value -> value.injectors().size()).orElse(0));
			data.addProperty("declarative_reacquisition_regions", declarative.map(value -> value.regions().size()).orElse(0));
			data.addProperty("declarative_reacquisition_failures", declarative.map(value -> value.cloneFailures().size()).orElse(0));

			MultiNoiseBiomeSource freshSource = MultiNoiseBiomeSource.createFromList(
				new Climate.ParameterList<>(snapshot.baseEntries())
			);
			TerraForgedChunkGenerator freshGenerator = new TerraForgedChunkGenerator(
				freshSource, noiseGenerator.generatorSettings()
			);
			PreviewRequest request = PreviewRequest.create(
				LevelStem.OVERWORLD,
				level.getSeed(),
				level.registryAccess(),
				level.registryAccess(),
				new LevelStem(level.dimensionTypeRegistration(), freshGenerator),
				"fresh_plain_source",
				"declarative_fixture",
				new TagEpoch(0L, "declarative_fixture")
			);
			var plan = MinecraftWorldgenPlanCompiler.compile(
				request,
				WorldgenCapabilityDiscovery.discover(getClass().getClassLoader()),
				WorldgenCompilationPurpose.BIOME_PREVIEW
			);
			data.addProperty("fresh_preview_source_class", freshSource.getClass().getName());
			data.addProperty("fresh_preview_decoration_executable", plan.selectionDecoration().executable());
			data.addProperty("fresh_preview_decoration_state", plan.selectionDecoration().descriptor().state().name());
			data.addProperty("fresh_preview_decoration_failure", plan.selectionDecoration().descriptor().firstCause().isPresent());
			return ProbeResult.complete(
				snapshot.cloneFailures().isEmpty()
					&& declarative.filter(value -> value.cloneFailures().isEmpty()).isPresent()
					&& plan.selectionDecoration().executable()
					&& plan.selectionDecoration().descriptor().firstCause().isEmpty()
					? TerminalState.PASS
					: TerminalState.FAIL,
				ProbePhase.GENERATION,
				data,
				snapshot.injectors().size() + snapshot.regions().size()
			);
		}
	}

	private static JsonObject criteria(
		LithostitchedInjectionBridge.ParameterCriteria criteria,
		RegistryOps<JsonElement> ops
	) {
		JsonObject result = new JsonObject();
		criteria.region().ifPresent(value -> result.addProperty("region", value.toString()));
		JsonArray climate = new JsonArray();
		for (var criterion : criteria.climate()) {
			JsonObject item = new JsonObject();
			item.addProperty("axis", criterion.axis().serializedName());
			item.addProperty("min_inclusive", criterion.range().minInclusive());
			item.addProperty("max_inclusive", criterion.range().maxInclusive());
			climate.add(item);
		}
		result.add("climate", climate);
		JsonArray density = new JsonArray();
		for (var criterion : criteria.density()) {
			JsonObject item = new JsonObject();
			item.addProperty("min_inclusive", criterion.range().minInclusive());
			item.addProperty("max_inclusive", criterion.range().maxInclusive());
			JsonElement declaration = DensityFunction.HOLDER_HELPER_CODEC
				.encodeStart(ops, criterion.declaration())
				.getOrThrow(message -> new IllegalStateException("density encode: " + message));
			item.add("declaration", declaration);
			density.add(item);
		}
		result.add("density", density);
		return result;
	}

	private static JsonArray holders(List<Holder<Biome>> holders, Registry<Biome> registry) {
		return strings(holders.stream().map(holder -> holderId(holder, registry)).sorted().toList());
	}

	private static String holderId(Holder<Biome> holder, Registry<Biome> registry) {
		return holder.unwrapKey().map(key -> key.location().toString())
			.orElseGet(() -> String.valueOf(registry.getKey(holder.value())));
	}

	private static JsonArray strings(Iterable<String> values) {
		JsonArray result = new JsonArray();
		for (String value : values) {
			result.add(value);
		}
		return result;
	}
}
