package org.squinchmods.investigate.rtf;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HexFormat;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeSet;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;

import net.minecraft.resources.ResourceKey;
import net.minecraft.server.MinecraftServer;
import net.minecraft.world.level.biome.Biome;
import net.minecraft.world.level.biome.Climate;
import net.minecraft.world.level.dimension.LevelStem;
import org.squinchmods.investigate.ProbeExecution;
import org.squinchmods.investigate.ProbePack;
import org.squinchmods.investigate.ProbePhase;
import org.squinchmods.investigate.ProbeRegistry;
import org.squinchmods.investigate.ProbeRequest;
import org.squinchmods.investigate.ProbeResult;
import org.squinchmods.investigate.TerminalState;
import raccoonman.reterraforged.world.worldgen.biolith.BiolithPlacementBridge;
import raccoonman.reterraforged.world.worldgen.runtime.CapabilityState;
import raccoonman.reterraforged.world.worldgen.runtime.TerraForgedChunkGenerator;
import raccoonman.reterraforged.world.worldgen.runtime.WorldgenBiomeSelection;

public final class BiolithSnapshotProbePack implements ProbePack {
	@Override
	public void register() {
		ProbeRegistry.register("squinch:ftf-biolith-snapshot", "1", SnapshotProbe::new);
	}

	private static final class SnapshotProbe implements ProbeExecution {
		private SnapshotProbe(ProbeRequest request) {
		}

		@Override
		public ProbeResult tick(MinecraftServer server) {
			var found = BiolithPlacementBridge.snapshot(LevelStem.OVERWORLD);
			if (found.isEmpty()) {
				JsonObject data = new JsonObject();
				data.addProperty("dimension", LevelStem.OVERWORLD.location().toString());
				return ProbeResult.complete(TerminalState.FAIL, ProbePhase.GENERATION, data, 0);
			}

			var snapshot = found.orElseThrow();
			JsonObject data = new JsonObject();
			data.addProperty("mechanism_version", snapshot.mechanismVersion());
			data.addProperty("dimension", snapshot.dimension().location().toString());
			data.addProperty("placement_count", snapshot.placements().size());
			data.addProperty("removal_count", snapshot.removals().size());
			data.addProperty("replacement_target_count", snapshot.replacements().size());
			data.addProperty("replacement_count", count(snapshot.replacements()));
			data.addProperty("sub_biome_target_count", snapshot.subBiomes().size());
			data.addProperty("sub_biome_count", count(snapshot.subBiomes()));

			List<BiolithPlacementBridge.Placement> placements = snapshot.placements().stream()
				.sorted(Comparator.comparing(BiolithSnapshotProbePack::placementKey))
				.toList();
			JsonArray placementData = new JsonArray();
			for (var placement : placements) {
				JsonObject item = new JsonObject();
				item.addProperty("biome", placement.biome().location().toString());
				item.addProperty("from_data", placement.fromData());
				item.add("point", point(placement.point()));
				placementData.add(item);
			}
			data.add("placements", placementData);

			data.add("removals", strings(snapshot.removals().stream()
				.map(value -> value.biome().location().toString() + ":from_data=" + value.fromData())
				.sorted()
				.toList()));

			JsonArray replacements = new JsonArray();
			for (var entry : sorted(snapshot.replacements())) {
				JsonObject target = new JsonObject();
				target.addProperty("target", entry.getKey().location().toString());
				JsonArray requests = new JsonArray();
				for (var replacement : entry.getValue()) {
					JsonObject item = new JsonObject();
					item.addProperty("biome", replacement.biome().location().toString());
					item.addProperty("proportion", replacement.proportion());
					item.addProperty("from_data", replacement.fromData());
					requests.add(item);
				}
				target.add("requests", requests);
				replacements.add(target);
			}
			data.add("replacements", replacements);

			JsonArray subBiomes = new JsonArray();
			List<String> criterionFailures = new ArrayList<>();
			for (var entry : sorted(snapshot.subBiomes())) {
				for (var subBiome : entry.getValue()) {
					JsonObject item = new JsonObject();
					item.addProperty("target", subBiome.target().location().toString());
					item.addProperty("biome", subBiome.biome().location().toString());
					item.addProperty("criterion_type", subBiome.criterionType().toString());
					item.addProperty("criterion_normalized", subBiome.criterionNormalized());
					subBiome.criterionFailure().ifPresent(failure -> {
						item.addProperty("criterion_failure", failure);
						criterionFailures.add(failure);
					});
					item.addProperty("from_data", subBiome.fromData());
					subBiomes.add(item);
				}
			}
			data.add("sub_biomes", subBiomes);
			data.add("criterion_failures", strings(criterionFailures.stream().sorted().distinct().toList()));

			Set<String> requestedOutputs = new TreeSet<>();
			snapshot.placements().forEach(value -> requestedOutputs.add(value.biome().location().toString()));
			snapshot.replacements().values().stream().flatMap(List::stream)
				.map(BiolithPlacementBridge.Replacement::biome)
				.map(ResourceKey::location)
				.map(Object::toString)
				.filter(value -> !value.equals("biolith:vanilla"))
				.forEach(requestedOutputs::add);
			snapshot.subBiomes().values().stream().flatMap(List::stream)
				.map(BiolithPlacementBridge.SubBiome::biome)
				.map(ResourceKey::location)
				.map(Object::toString)
				.forEach(requestedOutputs::add);
			TerraForgedChunkGenerator generator = (TerraForgedChunkGenerator) server.overworld()
				.getChunkSource().getGenerator();
			var plan = generator.plan().orElseThrow();
			var domains = plan.providerSelection().providers();
			Set<String> possibleOutputs = WorldgenBiomeSelection.possibleBiomes(plan).stream()
				.map(value -> value.unwrapKey().orElseThrow().location().toString())
				.collect(java.util.stream.Collectors.toCollection(TreeSet::new));
			boolean normalizedPlacementCoverage = !domains.isEmpty() && snapshot.placements().stream()
				.allMatch(placement -> domains.stream().allMatch(domain -> domain.candidates().values().stream()
					.anyMatch(entry -> entry.getFirst().equals(placement.point())
						&& entry.getSecond().is(placement.biome()))));
			boolean normalizedRemovalCoverage = snapshot.removals().stream().allMatch(removal ->
				domains.stream().allMatch(domain -> domain.candidates().values().stream()
					.noneMatch(entry -> entry.getSecond().is(removal.biome()))));
			boolean normalizedOutputCoverage = possibleOutputs.containsAll(requestedOutputs);
			boolean criteriaNormalized = criterionFailures.isEmpty();
			boolean selectionAvailable = plan.selectionDecoration().descriptor().state()
				!= CapabilityState.UNAVAILABLE;
			long normalizedCandidateCount = domains.stream()
				.mapToLong(domain -> domain.candidates().values().size()).sum();
			data.add("requested_outputs", strings(requestedOutputs));
			data.add("possible_outputs", strings(possibleOutputs));
			data.addProperty("criteria_normalized", criteriaNormalized);
			data.addProperty("selection_available", selectionAvailable);
			data.addProperty("normalized_provider_count", domains.size());
			data.addProperty("normalized_candidate_count", normalizedCandidateCount);
			data.addProperty("normalized_candidate_sha256", normalizedDigest(domains));
			data.addProperty("normalized_placement_coverage_complete", normalizedPlacementCoverage);
			data.addProperty("normalized_removal_coverage_complete", normalizedRemovalCoverage);
			data.addProperty("normalized_output_coverage_complete", normalizedOutputCoverage);

			boolean passed = criteriaNormalized && selectionAvailable
				&& normalizedPlacementCoverage && normalizedRemovalCoverage && normalizedOutputCoverage;
			return ProbeResult.complete(
				passed ? TerminalState.PASS : TerminalState.FAIL,
				ProbePhase.GENERATION,
				data,
				snapshot.placements().size() + snapshot.removals().size()
					+ count(snapshot.replacements()) + count(snapshot.subBiomes())
			);
		}
	}

	private static String normalizedDigest(
		List<raccoonman.reterraforged.world.worldgen.runtime.WorldgenPlans.ProviderDomain> domains
	) {
		try {
			MessageDigest digest = MessageDigest.getInstance("SHA-256");
			for (var domain : domains) {
				update(digest, domain.id().toString());
				for (var entry : domain.candidates().values()) {
					update(digest, pointKey(entry.getFirst()));
					update(digest, entry.getSecond().unwrapKey().orElseThrow().location().toString());
				}
			}
			return HexFormat.of().formatHex(digest.digest());
		} catch (java.security.NoSuchAlgorithmException failure) {
			throw new IllegalStateException(failure);
		}
	}

	private static void update(MessageDigest digest, String value) {
		digest.update(value.getBytes(StandardCharsets.UTF_8));
		digest.update((byte) 0);
	}

	private static <T> long count(Map<?, List<T>> values) {
		return values.values().stream().mapToLong(List::size).sum();
	}

	private static String placementKey(BiolithPlacementBridge.Placement placement) {
		return placement.biome().location() + ":" + pointKey(placement.point()) + ":" + placement.fromData();
	}

	private static String pointKey(Climate.ParameterPoint point) {
		return point.temperature().min() + ":" + point.temperature().max()
			+ ":" + point.humidity().min() + ":" + point.humidity().max()
			+ ":" + point.continentalness().min() + ":" + point.continentalness().max()
			+ ":" + point.erosion().min() + ":" + point.erosion().max()
			+ ":" + point.depth().min() + ":" + point.depth().max()
			+ ":" + point.weirdness().min() + ":" + point.weirdness().max()
			+ ":" + point.offset();
	}

	private static JsonObject point(Climate.ParameterPoint point) {
		JsonObject result = new JsonObject();
		result.add("temperature", range(point.temperature()));
		result.add("humidity", range(point.humidity()));
		result.add("continentalness", range(point.continentalness()));
		result.add("erosion", range(point.erosion()));
		result.add("depth", range(point.depth()));
		result.add("weirdness", range(point.weirdness()));
		result.addProperty("offset", point.offset());
		return result;
	}

	private static JsonArray range(Climate.Parameter parameter) {
		JsonArray result = new JsonArray();
		result.add(parameter.min());
		result.add(parameter.max());
		return result;
	}

	private static <T> List<Map.Entry<ResourceKey<Biome>, List<T>>> sorted(
		Map<ResourceKey<Biome>, List<T>> values
	) {
		List<Map.Entry<ResourceKey<Biome>, List<T>>> result = new ArrayList<>(values.entrySet());
		result.sort(Map.Entry.comparingByKey(Comparator.comparing(key -> key.location().toString())));
		return List.copyOf(result);
	}

	private static JsonArray strings(Iterable<String> values) {
		JsonArray result = new JsonArray();
		for (String value : values) {
			result.add(value);
		}
		return result;
	}
}
