package org.squinchmods.investigate.rtf;

import java.io.ByteArrayOutputStream;
import java.io.DataOutputStream;
import java.io.IOException;
import java.io.OutputStream;
import java.util.Arrays;
import java.util.zip.DeflaterOutputStream;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;

import net.minecraft.nbt.CompoundTag;
import net.minecraft.nbt.NbtIo;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import org.squinchmods.investigate.FinishedChunkSelection;
import org.squinchmods.investigate.ProbeExecution;
import org.squinchmods.investigate.ProbePack;
import org.squinchmods.investigate.ProbePhase;
import org.squinchmods.investigate.ProbeRegistry;
import org.squinchmods.investigate.ProbeRequest;
import org.squinchmods.investigate.ProbeResult;
import org.squinchmods.investigate.TerminalState;
import raccoonman.reterraforged.world.worldgen.ChunkFlowField;
import raccoonman.reterraforged.world.worldgen.IFlowFieldHolder;

public final class FlowStorageBenchmarkProbePack implements ProbePack {
	@Override
	public void register() {
		ProbeRegistry.register("squinch:rtf-flow-storage-benchmark", "1", Benchmark::new);
	}

	private static final class Benchmark implements ProbeExecution {
		private final FinishedChunkSelection selection;
		private final int warmupIterations;
		private final int measurementIterations;
		private final int repetitions;

		private Benchmark(ProbeRequest request) {
			JsonObject config = request.config();
			this.selection = new FinishedChunkSelection(config, "rtf-flow-storage-benchmark");
			this.warmupIterations = value(config, "warmup_iterations", 20_000);
			this.measurementIterations = value(config, "measurement_iterations", 100_000);
			this.repetitions = value(config, "repetitions", 7);
			if (this.warmupIterations < 1 || this.measurementIterations < 1 || this.repetitions < 3) {
				throw new IllegalArgumentException("benchmark iteration counts must be positive and repetitions >= 3");
			}
		}

		@Override
		public ProbeResult tick(MinecraftServer server) {
			ServerLevel level = server.overworld();
			FinishedChunkSelection.Snapshot snapshot = this.selection.poll(level);
			if (snapshot == null) {
				return null;
			}
			try {
				long riverChunks = 0;
				long settingsTags = 0;
				long flowNbtBytes = 0;
				for (FinishedChunkSelection.ReadyChunk ready : snapshot.ready()) {
					if (!(ready.chunk() instanceof IFlowFieldHolder holder)) {
						continue;
					}
					ChunkFlowField field = holder.reterraforged$getFlowField();
					if (!field.hasRivers()) {
						continue;
					}
					riverChunks++;
					CompoundTag tag = new CompoundTag();
					field.writeToNbt(tag);
					if (tag.contains("RTFFlowSettings")) {
						settingsTags++;
					}
					flowNbtBytes += uncompressedSize(tag);
				}

				ChunkFlowField synthetic = new ChunkFlowField();
				for (int z = 0; z < 16; z++) {
					for (int x = 0; x < 16; x++) {
						synthetic.setFlow(x, z, (byte) (((x + z) % 7) + 1));
					}
				}
				CompoundTag sample = new CompoundTag();
				synthetic.writeToNbt(sample);

				benchmarkWrite(synthetic, this.warmupIterations, false);
				benchmarkWrite(synthetic, this.warmupIterations, true);
				long[] tagOnly = new long[this.repetitions];
				long[] serialized = new long[this.repetitions];
				long checksum = 0;
				for (int repetition = 0; repetition < this.repetitions; repetition++) {
					Measurement first = benchmarkWrite(synthetic, this.measurementIterations, false);
					Measurement second = benchmarkWrite(synthetic, this.measurementIterations, true);
					tagOnly[repetition] = first.nanoseconds();
					serialized[repetition] = second.nanoseconds();
					checksum += first.checksum() + second.checksum();
				}

				JsonObject data = new JsonObject();
				data.addProperty("authority", "finished-chunk-flow-storage");
				data.addProperty("ready_chunks", snapshot.ready().size());
				data.addProperty("river_chunks", riverChunks);
				data.addProperty("chunks_with_flow_settings_nbt", settingsTags);
				data.addProperty("flow_nbt_uncompressed_bytes", flowNbtBytes);
				data.addProperty("sample_uncompressed_bytes", uncompressedSize(sample));
				data.addProperty("sample_deflate_bytes", deflateSize(sample));
				data.addProperty("sample_contains_settings", sample.contains("RTFFlowSettings"));
				data.addProperty("warmup_iterations", this.warmupIterations);
				data.addProperty("measurement_iterations", this.measurementIterations);
				data.addProperty("repetitions", this.repetitions);
				data.add("tag_write_ns_per_op", summary(tagOnly, this.measurementIterations));
				data.add("tag_and_nbt_write_ns_per_op", summary(serialized, this.measurementIterations));
				data.addProperty("checksum", checksum);
				return this.selection.result(snapshot, data);
			} catch (IOException error) {
				JsonObject data = new JsonObject();
				data.addProperty("error", error.toString());
				return ProbeResult.complete(TerminalState.ERROR, ProbePhase.FINISHED_CHUNK, data, 0);
			}
		}
	}

	private static Measurement benchmarkWrite(ChunkFlowField field, int iterations, boolean serialize) throws IOException {
		DataOutputStream sink = serialize ? new DataOutputStream(OutputStream.nullOutputStream()) : null;
		long checksum = 0;
		long started = System.nanoTime();
		for (int iteration = 0; iteration < iterations; iteration++) {
			CompoundTag tag = new CompoundTag();
			field.writeToNbt(tag);
			if (serialize) {
				NbtIo.write(tag, sink);
			}
			checksum += tag.size();
		}
		return new Measurement(System.nanoTime() - started, checksum);
	}

	private static int uncompressedSize(CompoundTag tag) throws IOException {
		ByteArrayOutputStream bytes = new ByteArrayOutputStream();
		NbtIo.write(tag, new DataOutputStream(bytes));
		return bytes.size();
	}

	private static int deflateSize(CompoundTag tag) throws IOException {
		ByteArrayOutputStream bytes = new ByteArrayOutputStream();
		try (DataOutputStream output = new DataOutputStream(new DeflaterOutputStream(bytes))) {
			NbtIo.write(tag, output);
		}
		return bytes.size();
	}

	private static JsonObject summary(long[] observations, int iterations) {
		double[] values = new double[observations.length];
		for (int index = 0; index < observations.length; index++) {
			values[index] = (double) observations[index] / iterations;
		}
		double[] ordered = values.clone();
		Arrays.sort(ordered);
		JsonArray samples = new JsonArray();
		for (double value : values) {
			samples.add(value);
		}
		JsonObject result = new JsonObject();
		result.add("observations", samples);
		result.addProperty("median", ordered[ordered.length / 2]);
		result.addProperty("min", ordered[0]);
		result.addProperty("max", ordered[ordered.length - 1]);
		return result;
	}

	private static int value(JsonObject config, String key, int fallback) {
		return config.has(key) ? config.get(key).getAsInt() : fallback;
	}

	private record Measurement(long nanoseconds, long checksum) {
	}
}
