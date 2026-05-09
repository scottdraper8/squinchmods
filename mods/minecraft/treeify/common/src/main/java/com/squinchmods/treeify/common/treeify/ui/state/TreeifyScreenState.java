package com.squinchmods.treeify.common.treeify.ui.state;

import java.util.Map;

public record TreeifyScreenState(
	String lastSearchText,
	double lastScrollAmount,
	Map<String, Boolean> collapsedGroups
)
{
	public TreeifyScreenState {
		lastSearchText = lastSearchText == null ? "" : lastSearchText;
		collapsedGroups = collapsedGroups == null ? Map.of() : Map.copyOf(collapsedGroups);
	}
}
