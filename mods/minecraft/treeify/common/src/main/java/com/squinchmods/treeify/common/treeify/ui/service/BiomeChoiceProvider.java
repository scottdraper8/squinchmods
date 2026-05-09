package com.squinchmods.treeify.common.treeify.ui.service;

import java.util.List;
import java.util.Optional;

public interface BiomeChoiceProvider
{
	List<BiomeChoice> choices();

	List<BiomeChoice> search(String query, int limit);

	Optional<BiomeChoice> byId(String id);
}
