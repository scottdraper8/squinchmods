package com.squinchmods.vegetate.common.vegetate.ui.service;

import dev.isxander.yacl3.gui.YACLScreen;
import java.util.Map;

public interface VegetateConfigSession
{
	String currentTabId();

	void setCurrentTabId(String tabId);

	String getSearchText(String screenId);

	void setSearchText(String screenId, String searchText);

	double getScrollAmount(String screenId);

	void setScrollAmount(String screenId, double scrollAmount);

	Map<String, Boolean> getCollapsedGroups(String screenId);

	void setCollapsedGroups(String screenId, Map<String, Boolean> collapsedGroups);

	void saveFrom(YACLScreen screen);

	void loadInto(YACLScreen screen);
}
