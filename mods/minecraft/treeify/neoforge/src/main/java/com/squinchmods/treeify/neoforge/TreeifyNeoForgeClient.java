package com.squinchmods.treeify.neoforge;

import com.squinchmods.treeify.common.TreeifyClient;
import net.neoforged.bus.api.IEventBus;
import net.neoforged.neoforge.client.event.RenderLevelStageEvent;

public final class TreeifyNeoForgeClient
{
	public static void init(IEventBus modEventBus, IEventBus eventBus) {
		TreeifyClient.init();
		eventBus.addListener(TreeifyNeoForgeClient::onRenderLevelStage);
	}

	private static void onRenderLevelStage(RenderLevelStageEvent event) {
	}
}
