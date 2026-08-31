package org.squinchmods.investigate.rtf;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HexFormat;
import java.util.LinkedHashSet;
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
import raccoonman.reterraforged.world.worldgen.runtime.TerraForgedChunkGenerator;

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
			data.addProperty("sealed", snapshot.sealed());
			data.addProperty("entries_complete", snapshot.entriesComplete());
			snapshot.finalizedWorld().ifPresent(value -> data.addProperty("finalized_world", value));
			snapshot.finalizedSeed().ifPresent(value -> data.addProperty("finalized_seed", value));
			data.addProperty("placement_count", snapshot.placements().size());
			data.addProperty("removal_count", snapshot.removals().size());
			data.addProperty("replacement_target_count", snapshot.replacements().size());
			data.addProperty("replacement_count", count(snapshot.replacements()));
			data.addProperty("sub_biome_target_count", snapshot.subBiomes().size());
			data.addProperty("sub_biome_count", count(snapshot.subBiomes()));
			data.addProperty("final_entry_count", snapshot.finalEntries().size());

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
				target.add("saved_order", strings(snapshot.savedOrders()
					.getOrDefault(entry.getKey(), List.of()).stream()
					.map(key -> key.location().toString())
					.toList()));
				replacements.add(target);
			}
			data.add("replacements", replacements);

			JsonArray subBiomes = new JsonArray();
			for (var entry : sorted(snapshot.subBiomes())) {
				for (var subBiome : entry.getValue()) {
					JsonObject item = new JsonObject();
					item.addProperty("target", subBiome.target().location().toString());
					item.addProperty("biome", subBiome.biome().location().toString());
					item.addProperty("criterion_type", subBiome.criterionType());
					item.addProperty("from_data", subBiome.fromData());
					subBiomes.add(item);
				}
			}
			data.add("sub_biomes", subBiomes);

			JsonArray emitted = new JsonArray();
			for (int index = 0; index < snapshot.finalEntries().size(); index++) {
				var entry = snapshot.finalEntries().get(index);
				JsonObject item = new JsonObject();
				item.addProperty("encounter_order", index);
				item.addProperty("biome", entry.biome().location().toString());
				item.add("point", point(entry.point()));
				emitted.add(item);
			}
			data.add("emitted_entries", emitted);

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
			Set<String> emittedOutputs = snapshot.finalEntries().stream()
				.map(BiolithPlacementBridge.FinalEntry::biome)
				.map(ResourceKey::location)
				.map(Object::toString)
				.collect(java.util.stream.Collectors.toCollection(TreeSet::new));
			boolean outputCoverageComplete = emittedOutputs.containsAll(requestedOutputs);
			boolean placementCoverageComplete = snapshot.placements().stream().allMatch(placement ->
				snapshot.finalEntries().contains(new BiolithPlacementBridge.FinalEntry(
					placement.biome(), placement.point()
				))
			);
			boolean savedOrdersComplete = snapshot.replacements().entrySet().stream().allMatch(entry ->
				completeOrder(entry.getValue(), snapshot.savedOrders().get(entry.getKey()))
			);
			boolean ownerMatches = snapshot.finalizedSeed().filter(seed -> seed == server.overworld().getSeed()).isPresent()
				&& snapshot.finalizedWorld().filter(LevelStem.OVERWORLD.location().toString()::equals).isPresent();
			TerraForgedChunkGenerator generator = (TerraForgedChunkGenerator) server.overworld()
				.getChunkSource().getGenerator();
			var plan = generator.plan().orElseThrow();
			var domains = plan.providerSelection().providers();
			boolean normalizedPlacementCoverage = !domains.isEmpty() && snapshot.placements().stream()
				.allMatch(placement -> domains.stream().allMatch(domain -> domain.candidates().values().stream()
					.anyMatch(entry -> entry.getFirst().equals(placement.point())
						&& entry.getSecond().is(placement.biome()))));
			boolean normalizedRemovalCoverage = snapshot.removals().stream().allMatch(removal ->
				domains.stream().allMatch(domain -> domain.candidates().values().stream()
					.noneMatch(entry -> entry.getSecond().is(removal.biome()))));
			boolean normalizedOutputCoverage = requestedOutputs.stream().allMatch(output ->
				domains.stream().allMatch(domain -> domain.candidates().values().stream()
					.anyMatch(entry -> entry.getSecond().unwrapKey()
						.map(key -> key.location().toString().equals(output)).orElse(false))));
			long normalizedCandidateCount = domains.stream()
				.mapToLong(domain -> domain.candidates().values().size()).sum();
			data.add("requested_outputs", strings(requestedOutputs));
			data.add("emitted_outputs", strings(emittedOutputs));
			data.addProperty("output_coverage_complete", outputCoverageComplete);
			data.addProperty("placement_coverage_complete", placementCoverageComplete);
			data.addProperty("saved_orders_complete", savedOrdersComplete);
			data.addProperty("owner_matches", ownerMatches);
			data.addProperty("normalized_provider_count", domains.size());
			data.addProperty("normalized_candidate_count", normalizedCandidateCount);
			data.addProperty("normalized_candidate_sha256", normalizedDigest(domains));
			data.addProperty("normalized_placement_coverage_complete", normalizedPlacementCoverage);
			data.addProperty("normalized_removal_coverage_complete", normalizedRemovalCoverage);
			data.addProperty("normalized_output_coverage_complete", normalizedOutputCoverage);

			boolean passed = snapshot.sealed() && snapshot.entriesComplete()
				&& outputCoverageComplete && placementCoverageComplete && savedOrdersComplete && ownerMatches
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

	private static boolean completeOrder(
		List<BiolithPlacementBridge.Replacement> requests,
		List<ResourceKey<Biome>> order
	) {
		if (order == null) {
			return false;
		}
		double maximum = requests.stream().mapToDouble(BiolithPlacementBridge.Replacement::proportion)
			.max().orElse(0.0D);
		if (maximum < 1.0D && order.stream().noneMatch(key -> key.location().toString().equals("biolith:vanilla"))) {
			return false;
		}
		return requests.stream()
			.filter(request -> request.proportion() > 0.0D)
			.allMatch(request -> order.contains(request.biome()));
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
