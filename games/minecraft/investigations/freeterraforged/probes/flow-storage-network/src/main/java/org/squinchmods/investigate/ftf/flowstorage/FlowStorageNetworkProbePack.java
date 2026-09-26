package org.squinchmods.investigate.ftf.flowstorage;

import com.google.gson.JsonObject;
import net.minecraft.server.MinecraftServer;
import org.squinchmods.investigate.ProbeExecution;
import org.squinchmods.investigate.ProbePack;
import org.squinchmods.investigate.ProbePhase;
import org.squinchmods.investigate.ProbeRegistry;
import org.squinchmods.investigate.ProbeRequest;
import org.squinchmods.investigate.ProbeResult;
import org.squinchmods.investigate.TerminalState;

public final class FlowStorageNetworkProbePack implements ProbePack {
	@Override
	public void register() {
		ProbeRegistry.register("squinch:ftf-flow-storage-network-arm", "1", Arm::new);
		ProbeRegistry.register("squinch:ftf-flow-storage-network-report", "1", Report::new);
	}

	private static final class Arm implements ProbeExecution {
		private final JsonObject config;

		private Arm(ProbeRequest request) {
			this.config = request.config().deepCopy();
		}

		@Override
		public ProbeResult tick(MinecraftServer server) {
			int requested = FlowStorageNetworkTelemetry.arm(this.config);
			JsonObject data = new JsonObject();
			data.addProperty("authority", "chunk-serializer-arm");
			data.addProperty("requested_chunks", requested);
			return ProbeResult.complete(TerminalState.PASS, ProbePhase.FINISHED_CHUNK, data, 0);
		}
	}

	private static final class Report implements ProbeExecution {
		private final int expectedChunks;

		private Report(ProbeRequest request) {
			this.expectedChunks = FlowStorageNetworkTelemetry.requestedChunks(request.config());
		}

		@Override
		public ProbeResult tick(MinecraftServer server) {
			FlowStorageNetworkTelemetry.Report report = FlowStorageNetworkTelemetry.report();
			JsonObject data = report.data();
			boolean complete = report.observedChunks() == this.expectedChunks && report.errors() == 0;
			data.addProperty("expected_chunks", this.expectedChunks);
			if (!complete) {
				data.addProperty("error", "serializer capture was incomplete or recorded an error");
			}
			return ProbeResult.complete(
				complete ? TerminalState.PASS : TerminalState.FAIL,
				ProbePhase.FINISHED_CHUNK,
				data,
				report.observedChunks()
			);
		}
	}
}
