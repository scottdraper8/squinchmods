package com.squinchmods.treeify.common.treeify.ui.control;

import com.squinchmods.treeify.common.treeify.ui.control.element.TreeifyBiomeControllerElement;
import com.squinchmods.treeify.common.treeify.ui.service.BiomeChoice;
import com.squinchmods.treeify.common.treeify.ui.service.BiomeChoiceProvider;
import dev.isxander.yacl3.api.Option;
import dev.isxander.yacl3.api.utils.Dimension;
import dev.isxander.yacl3.gui.AbstractWidget;
import dev.isxander.yacl3.gui.YACLScreen;
import dev.isxander.yacl3.gui.controllers.dropdown.AbstractDropdownController;
import net.minecraft.network.chat.Component;

import java.util.Comparator;
import java.util.List;
import java.util.Locale;
import java.util.Objects;
import java.util.Optional;
import java.util.stream.Stream;

public final class TreeifyBiomeController extends AbstractDropdownController<String>
{
	private static final int DEFAULT_SEARCH_LIMIT = 100;

	private final BiomeChoiceProvider choiceProvider;

	public TreeifyBiomeController(Option<String> option, BiomeChoiceProvider choiceProvider) {
		super(option, choiceProvider.choices().stream().map(BiomeChoice::id).toList(), false, false);
		this.choiceProvider = choiceProvider;
	}

	public BiomeChoiceProvider choiceProvider() {
		return this.choiceProvider;
	}

	public Optional<BiomeChoice> selectedChoice() {
		return this.choiceProvider.byId(getString());
	}

	public Optional<BiomeChoice> choice(String id) {
		return this.choiceProvider.byId(id);
	}

	public List<String> searchIds(String query) {
		return searchChoices(query, DEFAULT_SEARCH_LIMIT).stream().map(BiomeChoice::id).toList();
	}

	public List<BiomeChoice> searchChoices(String query, int limit) {
		if (query == null || query.isBlank()) {
			return this.choiceProvider.choices().stream()
				.limit(limit)
				.toList();
		}

		String normalizedQuery = normalize(query);
		Stream<BiomeChoice> providerMatches = this.choiceProvider.search(query, limit).stream();
		Stream<BiomeChoice> localMatches = this.choiceProvider.choices().stream()
			.filter(choice -> matches(choice, normalizedQuery));

		return Stream.concat(providerMatches, localMatches)
			.filter(Objects::nonNull)
			.distinct()
			.sorted(Comparator.comparingInt(choice -> score(choice, normalizedQuery)))
			.limit(limit)
			.toList();
	}

	@Override
	public String getString() {
		return option.pendingValue();
	}

	@Override
	public void setFromString(String value) {
		option.requestSet(value);
	}

	@Override
	protected String getValidValue(String value) {
		return this.getValidValue(value, 0);
	}

	@Override
	protected String getValidValue(String value, int offset) {
		if (value != null && !value.isBlank()) {
			List<String> validIds = searchIds(value);

			if (offset >= 0 && offset < validIds.size()) {
				return validIds.get(offset);
			}
		}

		return super.getValidValue(value, offset);
	}

	@Override
	public Component formatValue() {
		return this.choiceProvider.byId(getString())
			.map(choice -> choice.displayName().copy().append(" (" + choice.id() + ") "))
			.orElseGet(() -> Component.literal(getString()));
	}

	@Override
	public AbstractWidget provideWidget(YACLScreen screen, Dimension<Integer> widgetDimension) {
		return new TreeifyBiomeControllerElement(this, screen, widgetDimension);
	}

	private static boolean matches(BiomeChoice choice, String normalizedQuery) {
		return normalize(choice.id()).contains(normalizedQuery)
			|| normalize(choice.displayName().getString()).contains(normalizedQuery);
	}

	private static int score(BiomeChoice choice, String normalizedQuery) {
		String normalizedId = normalize(choice.id());
		String normalizedDisplayName = normalize(choice.displayName().getString());

		if (normalizedId.startsWith(normalizedQuery) || normalizedDisplayName.startsWith(normalizedQuery)) {
			return 0;
		}

		return 1;
	}

	private static String normalize(String value) {
		return value.toLowerCase(Locale.ROOT).replace(" ", "_");
	}
}
