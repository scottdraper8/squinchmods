package com.squinchmods.treeify.common.treeify.ui.option;

import com.google.common.collect.ImmutableList;
import dev.isxander.yacl3.api.Option;
import dev.isxander.yacl3.api.OptionDescription;
import dev.isxander.yacl3.api.OptionGroup;
import net.minecraft.network.chat.Component;
import org.apache.commons.lang3.Validate;
import org.jetbrains.annotations.ApiStatus.Internal;
import org.jetbrains.annotations.NotNull;

import java.util.ArrayList;
import java.util.Collection;
import java.util.List;

@Internal
public final class TreeifyInvisibleOptionGroup implements OptionGroup
{
	private final @NotNull Component name;
	private final @NotNull OptionDescription description;
	private final ImmutableList<? extends Option<?>> options;
	private final boolean collapsed;
	private final boolean root;

	public TreeifyInvisibleOptionGroup(
		@NotNull Component name,
		@NotNull OptionDescription description,
		ImmutableList<? extends Option<?>> options,
		boolean collapsed,
		boolean root
	) {
		this.name = name;
		this.description = description;
		this.options = options;
		this.collapsed = collapsed;
		this.root = root;
	}

	@Override
	public Component name() {
		return this.name;
	}

	@Override
	public OptionDescription description() {
		return this.description;
	}

	public @NotNull Component tooltip() {
		return this.description.text();
	}

	public @NotNull ImmutableList<? extends Option<?>> options() {
		return this.options;
	}

	public boolean collapsed() {
		return this.collapsed;
	}

	public boolean isRoot() {
		return this.root;
	}

	public static Builder createBuilder() {
		return new Builder();
	}

	@Internal
	public static final class Builder implements OptionGroup.Builder
	{
		private Component name = Component.empty();
		private OptionDescription description = OptionDescription.EMPTY;
		private final List<Option<?>> options = new ArrayList<>();
		private boolean collapsed;

		@Override
		public OptionGroup.Builder name(@NotNull Component name) {
			this.name = Validate.notNull(name, "`name` must not be null");
			return this;
		}

		@Override
		public OptionGroup.Builder description(@NotNull OptionDescription description) {
			this.description = Validate.notNull(description, "`description` must not be null");
			return this;
		}

		public Builder option(@NotNull Option<?> option) {
			this.options.add(Validate.notNull(option, "`option` must not be null"));
			return this;
		}

		public Builder options(@NotNull Collection<? extends Option<?>> options) {
			Validate.notEmpty(options, "`options` must not be empty");
			this.options.addAll(options);
			return this;
		}

		public Builder collapsed(boolean collapsed) {
			this.collapsed = collapsed;
			return this;
		}

		public TreeifyInvisibleOptionGroup build() {
			return new TreeifyInvisibleOptionGroup(
				this.name,
				this.description,
				ImmutableList.copyOf(this.options),
				this.collapsed,
				true
			);
		}
	}
}
