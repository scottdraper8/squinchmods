package com.squinchmods.treeify.common.treeify.ui.control;

import dev.isxander.yacl3.api.Controller;
import dev.isxander.yacl3.api.Option;
import dev.isxander.yacl3.api.controller.ValueFormatter;
import dev.isxander.yacl3.gui.controllers.BooleanController;
import dev.isxander.yacl3.impl.controller.BooleanControllerBuilderImpl;
import net.minecraft.network.chat.Component;
import org.apache.commons.lang3.Validate;

import java.util.function.Function;

public final class TreeifyBooleanDetailControllerBuilder extends BooleanControllerBuilderImpl
{
	private final String itemId;
	private boolean coloured;
	private ValueFormatter<Boolean> formatter = BooleanController.ON_OFF_FORMATTER::apply;
	private TreeifyBooleanDetailController.OpenDetailCallback openDetailCallback;
	private Function<String, Component> detailTooltipFormatter = id -> Component.literal(id);

	private TreeifyBooleanDetailControllerBuilder(Option<Boolean> option, String itemId) {
		super(option);
		this.itemId = itemId;
	}

	public TreeifyBooleanDetailControllerBuilder coloured(boolean coloured) {
		this.coloured = coloured;
		return this;
	}

	public TreeifyBooleanDetailControllerBuilder formatValue(ValueFormatter<Boolean> formatter) {
		this.formatter = Validate.notNull(formatter, "`formatter` cannot be null");
		return this;
	}

	public TreeifyBooleanDetailControllerBuilder onOffFormatter() {
		this.formatter = BooleanController.ON_OFF_FORMATTER::apply;
		return this;
	}

	public TreeifyBooleanDetailControllerBuilder yesNoFormatter() {
		this.formatter = BooleanController.YES_NO_FORMATTER::apply;
		return this;
	}

	public TreeifyBooleanDetailControllerBuilder trueFalseFormatter() {
		this.formatter = BooleanController.TRUE_FALSE_FORMATTER::apply;
		return this;
	}

	public TreeifyBooleanDetailControllerBuilder openDetailCallback(TreeifyBooleanDetailController.OpenDetailCallback openDetailCallback) {
		this.openDetailCallback = Validate.notNull(openDetailCallback, "`openDetailCallback` cannot be null");
		return this;
	}

	public TreeifyBooleanDetailControllerBuilder detailTooltip(Component detailTooltip) {
		Validate.notNull(detailTooltip, "`detailTooltip` cannot be null");
		this.detailTooltipFormatter = id -> detailTooltip;
		return this;
	}

	public TreeifyBooleanDetailControllerBuilder detailTooltipFormatter(Function<String, Component> detailTooltipFormatter) {
		this.detailTooltipFormatter = Validate.notNull(detailTooltipFormatter, "`detailTooltipFormatter` cannot be null");
		return this;
	}

	@Override
	public Controller<Boolean> build() {
		Validate.notNull(this.openDetailCallback, "`openDetailCallback` must not be null when building TreeifyBooleanDetailController");

		return new TreeifyBooleanDetailController(
			this.option,
			this.itemId,
			this.formatter::format,
			this.coloured,
			this.openDetailCallback,
			this.detailTooltipFormatter
		);
	}

	public static TreeifyBooleanDetailControllerBuilder create(Option<Boolean> option, String itemId) {
		return new TreeifyBooleanDetailControllerBuilder(option, itemId);
	}
}
