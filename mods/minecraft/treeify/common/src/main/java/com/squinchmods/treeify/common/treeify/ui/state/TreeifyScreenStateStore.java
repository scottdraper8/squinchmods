package com.squinchmods.treeify.common.treeify.ui.state;

import dev.isxander.yacl3.gui.YACLScreen;

import java.util.HashMap;
import java.util.Map;
import java.util.Optional;

public final class TreeifyScreenStateStore
{
	private final Map<String, TreeifyScreenState> states = new HashMap<>();

	public void save(YACLScreen screen) {
		String screenKey = screenKey(screen);
		TreeifyYaclStateAccess.capture(screen).ifPresent(state -> this.states.put(screenKey, state));
	}

	public void restore(YACLScreen screen) {
		get(screenKey(screen)).ifPresent(state -> TreeifyYaclStateAccess.restore(screen, state));
	}

	public void clear() {
		this.states.clear();
	}

	public Optional<TreeifyScreenState> get(String screenKey) {
		return Optional.ofNullable(this.states.get(screenKey));
	}

	private static String screenKey(YACLScreen screen) {
		return screen.getTitle().getString();
	}
}
