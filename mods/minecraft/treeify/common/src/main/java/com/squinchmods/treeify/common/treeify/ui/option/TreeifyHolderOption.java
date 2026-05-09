package com.squinchmods.treeify.common.treeify.ui.option;

import com.squinchmods.treeify.common.treeify.ui.control.TreeifyDualController;
import com.google.common.collect.ImmutableSet;
import dev.isxander.yacl3.api.Binding;
import dev.isxander.yacl3.api.Controller;
import dev.isxander.yacl3.api.Option;
import dev.isxander.yacl3.api.OptionDescription;
import dev.isxander.yacl3.api.OptionEventListener;
import dev.isxander.yacl3.api.OptionFlag;
import dev.isxander.yacl3.api.StateManager;
import dev.isxander.yacl3.api.controller.ControllerBuilder;
import dev.isxander.yacl3.impl.OptionImpl;
import net.minecraft.ChatFormatting;
import net.minecraft.network.chat.Component;
import org.apache.commons.lang3.Validate;
import org.jetbrains.annotations.ApiStatus;
import org.jetbrains.annotations.NotNull;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collection;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import java.util.function.BiConsumer;
import java.util.function.Function;

@ApiStatus.Internal
public final class TreeifyHolderOption<K extends Option<?>, V extends Option<?>> extends OptionImpl<TreeifyOptionPair<K, V>>
{
	private final TreeifyOptionPair<K, V> optionPair;
	private final K firstOption;
	private final V secondOption;

	private TreeifyHolderOption(
		@NotNull Component name,
		@NotNull Function<TreeifyOptionPair<K, V>, OptionDescription> descriptionFunction,
		@NotNull Function<Option<TreeifyOptionPair<K, V>>, TreeifyDualController<K, V>> controlGetter,
		@NotNull StateManager<TreeifyOptionPair<K, V>> stateManager,
		boolean available,
		@NotNull ImmutableSet<OptionFlag> flags,
		@NotNull Collection<OptionEventListener<TreeifyOptionPair<K, V>>> listeners
	) {
		super(
			name,
			descriptionFunction,
			opt -> controlGetter.apply(opt),
			stateManager,
			available,
			flags,
			listeners
		);

		this.optionPair = stateManager.get();
		this.firstOption = this.optionPair.firstOption();
		this.secondOption = this.optionPair.secondOption();
	}

	@Override
	public boolean available() {
		return this.firstOption.available() && this.secondOption.available();
	}

	@Override
	public void setAvailable(boolean available) {
		boolean firstChanged = this.firstOption.available() != available;
		boolean secondChanged = this.secondOption.available() != available;

		this.firstOption.setAvailable(available);
		this.secondOption.setAvailable(available);

		if (firstChanged || secondChanged) {
			if (!available) {
				this.firstOption.stateManager().sync();
				this.secondOption.stateManager().sync();
			}

			super.setAvailable(available);
		}
	}

	public static <K extends Option<?>, V extends Option<?>> TreeifyHolderOptionBuilder<K, V> createBuilder() {
		return new TreeifyHolderOptionBuilder<>();
	}

	public static <K extends Option<?>, V extends Option<?>> TreeifyHolderOptionBuilder<K, V> createBuilder(TreeifyOptionPair<K, V> optionPair) {
		return new TreeifyHolderOptionBuilder<K, V>().optionPair(optionPair);
	}

	private static final class PairStateManager<K extends Option<?>, V extends Option<?>> implements StateManager<TreeifyOptionPair<K, V>>
	{
		private final TreeifyOptionPair<K, V> optionPair;
		private final K firstOption;
		private final V secondOption;
		private final List<StateListener<TreeifyOptionPair<K, V>>> listeners = new ArrayList<>();

		private PairStateManager(@NotNull TreeifyOptionPair<K, V> optionPair) {
			this.optionPair = optionPair;
			this.firstOption = optionPair.firstOption();
			this.secondOption = optionPair.secondOption();

			this.firstOption.stateManager().addListener((oldValue, newValue) -> fire());
			this.secondOption.stateManager().addListener((oldValue, newValue) -> fire());
		}

		@Override
		public void set(TreeifyOptionPair<K, V> value) {
			Validate.notNull(value, "`value` cannot be null");

			boolean samePair = value.firstOption() == this.firstOption && value.secondOption() == this.secondOption;
			Validate.isTrue(samePair, "TreeifyHolderOption does not support replacing its option pair");

			fire();
		}

		@Override
		public TreeifyOptionPair<K, V> get() {
			return this.optionPair;
		}

		@Override
		public void apply() {
			this.firstOption.applyValue();
			this.secondOption.applyValue();
		}

		@Override
		public void resetToDefault(ResetAction action) {
			this.firstOption.stateManager().resetToDefault(action);
			this.secondOption.stateManager().resetToDefault(action);
		}

		@Override
		public void sync() {
			this.firstOption.stateManager().sync();
			this.secondOption.stateManager().sync();
		}

		@Override
		public boolean isSynced() {
			return this.firstOption.stateManager().isSynced() && this.secondOption.stateManager().isSynced();
		}

		@Override
		public boolean isAlwaysSynced() {
			return this.firstOption.stateManager().isAlwaysSynced() && this.secondOption.stateManager().isAlwaysSynced();
		}

		@Override
		public boolean isDefault() {
			return this.firstOption.stateManager().isDefault() && this.secondOption.stateManager().isDefault();
		}

		@Override
		public void addListener(StateListener<TreeifyOptionPair<K, V>> stateListener) {
			Validate.notNull(stateListener, "`stateListener` cannot be null");
			this.listeners.add(stateListener);
		}

		private void fire() {
			for (StateListener<TreeifyOptionPair<K, V>> listener : this.listeners) {
				listener.onStateChange(this.optionPair, this.optionPair);
			}
		}
	}

	@ApiStatus.Internal
	public static final class TreeifyHolderOptionBuilder<K extends Option<?>, V extends Option<?>> implements Builder<TreeifyOptionPair<K, V>>
	{
		private Component name = Component.literal("Name not specified!").withStyle(ChatFormatting.RED);
		private Function<TreeifyOptionPair<K, V>, OptionDescription> descriptionFunction = pending -> OptionDescription.EMPTY;
		private Function<Option<TreeifyOptionPair<K, V>>, TreeifyDualController<K, V>> controlGetter;
		private TreeifyOptionPair<K, V> optionPair;
		private boolean available = true;
		private boolean customDescription;
		private final Set<OptionFlag> flags = new HashSet<>();
		private final List<OptionEventListener<TreeifyOptionPair<K, V>>> listeners = new ArrayList<>();

		@Override
		public Builder<TreeifyOptionPair<K, V>> name(@NotNull Component name) {
			Validate.notNull(name, "`name` cannot be null");
			this.name = name;
			return this;
		}

		@Override
		public Builder<TreeifyOptionPair<K, V>> description(@NotNull OptionDescription description) {
			Validate.notNull(description, "`description` cannot be null");
			return description(pending -> description);
		}

		@Override
		public Builder<TreeifyOptionPair<K, V>> description(@NotNull Function<TreeifyOptionPair<K, V>, OptionDescription> descriptionFunction) {
			Validate.notNull(descriptionFunction, "`descriptionFunction` cannot be null");
			this.descriptionFunction = descriptionFunction;
			this.customDescription = true;
			return this;
		}

		@Override
		public Builder<TreeifyOptionPair<K, V>> controller(@NotNull Function<Option<TreeifyOptionPair<K, V>>, ControllerBuilder<TreeifyOptionPair<K, V>>> controllerBuilder) {
			Validate.notNull(controllerBuilder, "`controllerBuilder` cannot be null");
			return customController(opt -> controllerBuilder.apply(opt).build());
		}

		@Override
		@SuppressWarnings("unchecked")
		public Builder<TreeifyOptionPair<K, V>> customController(@NotNull Function<Option<TreeifyOptionPair<K, V>>, Controller<TreeifyOptionPair<K, V>>> control) {
			Validate.notNull(control, "`control` cannot be null");
			this.controlGetter = opt -> (TreeifyDualController<K, V>) control.apply(opt);
			return this;
		}

		@Override
		public Builder<TreeifyOptionPair<K, V>> stateManager(@NotNull StateManager<TreeifyOptionPair<K, V>> stateManager) {
			throw new UnsupportedOperationException("TreeifyHolderOption uses its own state manager. Use the child options' state managers instead.");
		}

		@Override
		public Builder<TreeifyOptionPair<K, V>> binding(@NotNull Binding<TreeifyOptionPair<K, V>> binding) {
			throw new UnsupportedOperationException("TreeifyHolderOption does not support binding(). Bind the child options instead.");
		}

		@Override
		public Builder<TreeifyOptionPair<K, V>> binding(
			@NotNull TreeifyOptionPair<K, V> def,
			@NotNull java.util.function.Supplier<@NotNull TreeifyOptionPair<K, V>> getter,
			@NotNull java.util.function.Consumer<@NotNull TreeifyOptionPair<K, V>> setter
		) {
			throw new UnsupportedOperationException("TreeifyHolderOption does not support binding(). Bind the child options instead.");
		}

		public TreeifyHolderOptionBuilder<K, V> optionPair(@NotNull TreeifyOptionPair<K, V> optionPair) {
			Validate.notNull(optionPair, "`optionPair` cannot be null");
			this.optionPair = optionPair;
			return this;
		}

		@Override
		public Builder<TreeifyOptionPair<K, V>> available(boolean available) {
			this.available = available;
			return this;
		}

		@Override
		public Builder<TreeifyOptionPair<K, V>> flag(@NotNull OptionFlag... flag) {
			Validate.notNull(flag, "`flag` must not be null");
			this.flags.addAll(Arrays.asList(flag));
			return this;
		}

		@Override
		public Builder<TreeifyOptionPair<K, V>> flags(@NotNull Collection<? extends OptionFlag> flags) {
			Validate.notNull(flags, "`flags` must not be null");
			this.flags.addAll(flags);
			return this;
		}

		@Override
		public Builder<TreeifyOptionPair<K, V>> addListener(@NotNull OptionEventListener<TreeifyOptionPair<K, V>> optionEventListener) {
			Validate.notNull(optionEventListener, "`optionEventListener` must not be null");
			this.listeners.add(optionEventListener);
			return this;
		}

		@Override
		public Builder<TreeifyOptionPair<K, V>> addListeners(@NotNull Collection<OptionEventListener<TreeifyOptionPair<K, V>>> listeners) {
			Validate.notNull(listeners, "`listeners` must not be null");
			this.listeners.addAll(listeners);
			return this;
		}

		@Override
		@Deprecated
		public Builder<TreeifyOptionPair<K, V>> instant(boolean instant) {
			throw new UnsupportedOperationException("TreeifyHolderOption does not support instant(). Use the child options' state managers instead.");
		}

		@Override
		@Deprecated
		public Builder<TreeifyOptionPair<K, V>> listener(@NotNull BiConsumer<Option<TreeifyOptionPair<K, V>>, TreeifyOptionPair<K, V>> listener) {
			Validate.notNull(listener, "`listener` must not be null");
			return addListener((opt, event) -> listener.accept(opt, opt.pendingValue()));
		}

		@Override
		@Deprecated
		public Builder<TreeifyOptionPair<K, V>> listeners(@NotNull Collection<BiConsumer<Option<TreeifyOptionPair<K, V>>, TreeifyOptionPair<K, V>>> listeners) {
			Validate.notNull(listeners, "`listeners` must not be null");

			for (BiConsumer<Option<TreeifyOptionPair<K, V>>, TreeifyOptionPair<K, V>> listener : listeners) {
				listener(listener);
			}

			return this;
		}

		@Override
		public Option<TreeifyOptionPair<K, V>> build() {
			Validate.notNull(this.optionPair, "`optionPair` must not be null when building TreeifyHolderOption");
			Validate.notNull(this.controlGetter, "`control` must not be null when building TreeifyHolderOption");

			K firstOption = this.optionPair.firstOption();
			V secondOption = this.optionPair.secondOption();
			Component combinedName = firstOption.name().copy().append(" & ").append(secondOption.name().copy());
			Function<TreeifyOptionPair<K, V>, OptionDescription> combinedDescriptionFunction =
				pending -> OptionDescription.of(
					firstOption.description().text().copy()
						.append("\n\n")
						.append(secondOption.description().text())
				);
			StateManager<TreeifyOptionPair<K, V>> stateManager = new PairStateManager<>(this.optionPair);
			Function<TreeifyOptionPair<K, V>, OptionDescription> effectiveDescriptionFunction = this.customDescription
				? this.descriptionFunction
				: combinedDescriptionFunction;

			return new TreeifyHolderOption<>(
				combinedName,
				effectiveDescriptionFunction,
				this.controlGetter,
				stateManager,
				this.available,
				ImmutableSet.copyOf(this.flags),
				this.listeners
			);
		}
	}
}
