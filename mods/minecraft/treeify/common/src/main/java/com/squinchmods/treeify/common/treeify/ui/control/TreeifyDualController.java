package com.squinchmods.treeify.common.treeify.ui.control;

import com.squinchmods.treeify.common.treeify.ui.control.element.TreeifyDualControllerElement;
import com.squinchmods.treeify.common.treeify.ui.option.TreeifyOptionPair;
import dev.isxander.yacl3.api.Controller;
import dev.isxander.yacl3.api.Option;
import dev.isxander.yacl3.api.utils.Dimension;
import dev.isxander.yacl3.gui.AbstractWidget;
import dev.isxander.yacl3.gui.TextScaledButtonWidget;
import dev.isxander.yacl3.gui.YACLScreen;
import net.minecraft.network.chat.Component;

public record TreeifyDualController<K extends Option<?>, V extends Option<?>>(
	TreeifyOptionPair<K, V> optionPair
) implements Controller<TreeifyOptionPair<K, V>>
{
	private static final double FIRST_WIDGET_WIDTH_RATIO = 0.5D;
	private static final Component RESET_LABEL = Component.literal("\u21BB");
	private static final String VALUE_SEPARATOR = " | ";

	@Override
	public Option<TreeifyOptionPair<K, V>> option() {
		return null;
	}

	@Override
	public Component formatValue() {
		return this.optionPair.firstOption().controller().formatValue().copy()
			.append(VALUE_SEPARATOR)
			.append(this.optionPair.secondOption().controller().formatValue());
	}

	@Override
	public AbstractWidget provideWidget(YACLScreen screen, Dimension<Integer> widgetDimension) {
		Dimension<Integer> firstWidgetDimension = widgetDimension.withWidth((int) (widgetDimension.width() * FIRST_WIDGET_WIDTH_RATIO));
		Dimension<Integer> secondWidgetDimension = widgetDimension
			.moved(firstWidgetDimension.width(), 0)
			.withWidth(widgetDimension.width() - firstWidgetDimension.width());

		AbstractWidget firstOptionWidget = this.optionPair.firstOption().controller().provideWidget(screen, firstWidgetDimension);
		AbstractWidget secondOptionWidget = this.optionPair.secondOption().controller().provideWidget(screen, secondWidgetDimension);
		TextScaledButtonWidget resetButtonWidget = null;

		if (canShowSharedReset(firstOptionWidget, secondOptionWidget)) {
			firstOptionWidget.setDimension(firstOptionWidget.getDimension().expanded(-10, 0));
			secondOptionWidget.setDimension(secondOptionWidget.getDimension().expanded(-10, 0));

			resetButtonWidget = new TextScaledButtonWidget(
				screen,
				secondOptionWidget.getDimension().xLimit() - 10,
				widgetDimension.y(),
				20,
				20,
				2.0F,
				RESET_LABEL,
				button -> {
					this.optionPair.firstOption().requestSetDefault();
					this.optionPair.secondOption().requestSetDefault();
				}
			);

			TextScaledButtonWidget resetButton = resetButtonWidget;
			this.optionPair.firstOption().addListener((opt, val) -> resetButton.active = canResetBothOptions());
			this.optionPair.secondOption().addListener((opt, val) -> resetButton.active = canResetBothOptions());
			resetButtonWidget.active = canResetBothOptions();
		}

		return new TreeifyDualControllerElement(widgetDimension, firstOptionWidget, secondOptionWidget, resetButtonWidget);
	}

	private boolean canShowSharedReset(AbstractWidget firstOptionWidget, AbstractWidget secondOptionWidget) {
		return this.optionPair.firstOption().controller().option().canResetToDefault()
			&& firstOptionWidget.canReset()
			&& this.optionPair.secondOption().controller().option().canResetToDefault()
			&& secondOptionWidget.canReset();
	}

	private boolean canResetBothOptions() {
		return !this.optionPair.firstOption().isPendingValueDefault()
			&& this.optionPair.firstOption().available()
			&& !this.optionPair.secondOption().isPendingValueDefault()
			&& this.optionPair.secondOption().available();
	}
}
