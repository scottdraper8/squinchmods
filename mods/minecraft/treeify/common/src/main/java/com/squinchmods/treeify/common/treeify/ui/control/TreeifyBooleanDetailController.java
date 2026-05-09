package com.squinchmods.treeify.common.treeify.ui.control;

import dev.isxander.yacl3.api.Option;
import dev.isxander.yacl3.api.utils.Dimension;
import dev.isxander.yacl3.gui.AbstractWidget;
import dev.isxander.yacl3.gui.TextScaledButtonWidget;
import dev.isxander.yacl3.gui.YACLScreen;
import dev.isxander.yacl3.gui.controllers.BooleanController;
import net.minecraft.client.gui.components.Tooltip;
import net.minecraft.client.gui.narration.NarrationElementOutput;
import net.minecraft.network.chat.Component;

import java.util.function.Function;

//? if >= 1.21.9 {
import net.minecraft.client.input.CharacterEvent;
import net.minecraft.client.input.KeyEvent;
import net.minecraft.client.input.MouseButtonEvent;
//?}

//? if >= 26.1 {
import net.minecraft.client.gui.GuiGraphicsExtractor;
//?} else {
/*import net.minecraft.client.gui.GuiGraphics;
*///?}

public class TreeifyBooleanDetailController extends BooleanController
{
	@FunctionalInterface
	public interface OpenDetailCallback {
		void open(YACLScreen parentScreen, String itemId);
	}

	private final String itemId;
	private final OpenDetailCallback openDetailCallback;
	private final Function<String, Component> detailTooltipFormatter;

	public TreeifyBooleanDetailController(
		Option<Boolean> option,
		String itemId,
		Function<Boolean, Component> valueFormatter,
		boolean coloured,
		OpenDetailCallback openDetailCallback,
		Function<String, Component> detailTooltipFormatter
	) {
		super(option, valueFormatter, coloured);
		this.itemId = itemId;
		this.openDetailCallback = openDetailCallback;
		this.detailTooltipFormatter = detailTooltipFormatter;
	}

	@Override
	public AbstractWidget provideWidget(YACLScreen screen, Dimension<Integer> widgetDimension) {
		return new BooleanWithDetailButtonWidget(
			super.provideWidget(screen, widgetDimension),
			screen,
			widgetDimension,
			this.itemId,
			this.openDetailCallback,
			this.detailTooltipFormatter
		);
	}

	public static final class BooleanWithDetailButtonWidget extends AbstractWidget
	{
		private static final int DETAIL_BUTTON_WIDTH = 20;
		private static final int DETAIL_BUTTON_HEIGHT = 20;
		private static final Component DETAIL_BUTTON_LABEL = Component.literal("\u2699").withStyle(style -> style.withBold(true));

		private final YACLScreen screen;
		private final String itemId;
		private final OpenDetailCallback openDetailCallback;
		private final AbstractWidget booleanElement;
		private final TextScaledButtonWidget detailButton;
		private boolean focused;

		public BooleanWithDetailButtonWidget(
			AbstractWidget booleanWidget,
			YACLScreen screen,
			Dimension<Integer> dim,
			String itemId,
			OpenDetailCallback openDetailCallback,
			Function<String, Component> detailTooltipFormatter
		) {
			super(dim);

			this.screen = screen;
			this.itemId = itemId;
			this.openDetailCallback = openDetailCallback;
			this.booleanElement = booleanWidget;
			this.detailButton = new TextScaledButtonWidget(
				screen,
				0,
				0,
				DETAIL_BUTTON_WIDTH,
				DETAIL_BUTTON_HEIGHT,
				1.0F,
				DETAIL_BUTTON_LABEL,
				button -> this.openDetailCallback.open(this.screen, this.itemId)
			);

			this.detailButton.setTooltip(Tooltip.create(detailTooltipFormatter.apply(itemId)));
			this.setDimension(dim);
		}

		@Override
		public void setDimension(Dimension<Integer> dim) {
			super.setDimension(dim);

			int booleanWidth = Math.max(0, dim.width() - DETAIL_BUTTON_WIDTH);
			this.booleanElement.setDimension(dim.withWidth(booleanWidth));
			this.detailButton.setX(dim.xLimit() - DETAIL_BUTTON_WIDTH);
			this.detailButton.setY(dim.y());
		}

		//? if >= 21.6 {
		@Override
		public void extractRenderState(GuiGraphicsExtractor graphics, int mouseX, int mouseY, float tickDelta) {
			this.booleanElement.extractRenderState(graphics, mouseX, mouseY, tickDelta);
			this.detailButton.active = this.booleanElement.isActive();
			this.detailButton.setY(getDimension().y());
			this.detailButton.extractRenderState(graphics, mouseX, mouseY, tickDelta);
		}
		//?} else {
		/*@Override
		public void render(GuiGraphics graphics, int mouseX, int mouseY, float tickDelta) {
			this.booleanElement.render(graphics, mouseX, mouseY, tickDelta);
			this.detailButton.active = this.booleanElement.isActive();
			this.detailButton.setY(getDimension().y());
			this.detailButton.render(graphics, mouseX, mouseY, tickDelta);
		}
		*///?}

		@Override
		public boolean canReset() {
			return true;
		}

		@Override
		public void mouseMoved(double mouseX, double mouseY) {
			this.detailButton.mouseMoved(mouseX, mouseY);
			this.booleanElement.mouseMoved(mouseX, mouseY);
		}

		@Override
		public boolean matchesSearch(String query) {
			return this.booleanElement.matchesSearch(query);
		}

		@Override
		public NarrationPriority narrationPriority() {
			return this.booleanElement.narrationPriority();
		}

		@Override
		public void updateNarration(NarrationElementOutput builder) {
			this.booleanElement.updateNarration(builder);
		}

		@Override
		public void unfocus() {
			this.focused = false;
			this.booleanElement.unfocus();
			this.detailButton.setFocused(false);
			super.unfocus();
		}

		@Override
		public void setFocused(boolean focused) {
			this.focused = focused;

			if (!focused) {
				this.booleanElement.setFocused(false);
				this.detailButton.setFocused(false);
				return;
			}

			this.booleanElement.setFocused(true);
			this.detailButton.setFocused(false);
		}

		@Override
		public boolean isFocused() {
			return this.focused || this.booleanElement.isFocused() || this.detailButton.isFocused();
		}

		@Override
		public boolean isMouseOver(double mouseX, double mouseY) {
			return this.detailButton.isMouseOver(mouseX, mouseY) || this.booleanElement.isMouseOver(mouseX, mouseY);
		}

		//? if >= 1.21.9 {
		@Override
		public boolean mouseClicked(MouseButtonEvent mouseButtonEvent, boolean doubleClick) {
			this.detailButton.active = this.booleanElement.isActive();

			if (this.detailButton.isMouseOver(mouseButtonEvent.x(), mouseButtonEvent.y())) {
				this.booleanElement.setFocused(false);
				this.detailButton.setFocused(true);
				this.focused = true;

				if (this.detailButton.mouseClicked(mouseButtonEvent, doubleClick)) {
					return true;
				}
			}

			this.detailButton.setFocused(false);
			this.booleanElement.setFocused(true);
			this.focused = true;

			return this.booleanElement.mouseClicked(mouseButtonEvent, doubleClick);
		}

		@Override
		public boolean mouseReleased(MouseButtonEvent mouseButtonEvent) {
			return this.detailButton.mouseReleased(mouseButtonEvent) || this.booleanElement.mouseReleased(mouseButtonEvent);
		}

		@Override
		public boolean mouseDragged(MouseButtonEvent mouseButtonEvent, double dx, double dy) {
			return this.detailButton.mouseDragged(mouseButtonEvent, dx, dy) || this.booleanElement.mouseDragged(mouseButtonEvent, dx, dy);
		}

		@Override
		public boolean keyPressed(KeyEvent keyEvent) {
			if (this.detailButton.isFocused() && this.detailButton.keyPressed(keyEvent)) {
				return true;
			}

			return this.booleanElement.keyPressed(keyEvent);
		}

		@Override
		public boolean keyReleased(KeyEvent keyEvent) {
			if (this.detailButton.isFocused() && this.detailButton.keyReleased(keyEvent)) {
				return true;
			}

			return this.booleanElement.keyReleased(keyEvent);
		}

		@Override
		public boolean charTyped(CharacterEvent characterEvent) {
			if (this.detailButton.isFocused() && this.detailButton.charTyped(characterEvent)) {
				return true;
			}

			return this.booleanElement.charTyped(characterEvent);
		}
		//?} else {
		/*@Override
		public boolean mouseClicked(double mouseX, double mouseY, int button) {
			this.detailButton.active = this.booleanElement.isActive();

			if (this.detailButton.isMouseOver(mouseX, mouseY)) {
				this.booleanElement.setFocused(false);
				this.detailButton.setFocused(true);
				this.focused = true;

				if (this.detailButton.mouseClicked(mouseX, mouseY, button)) {
					return true;
				}
			}

			this.detailButton.setFocused(false);
			this.booleanElement.setFocused(true);
			this.focused = true;

			return this.booleanElement.mouseClicked(mouseX, mouseY, button);
		}

		@Override
		public boolean mouseReleased(double mouseX, double mouseY, int button) {
			return this.detailButton.mouseReleased(mouseX, mouseY, button) || this.booleanElement.mouseReleased(mouseX, mouseY, button);
		}

		@Override
		public boolean mouseDragged(double mouseX, double mouseY, int button, double deltaX, double deltaY) {
			return this.detailButton.mouseDragged(mouseX, mouseY, button, deltaX, deltaY) || this.booleanElement.mouseDragged(mouseX, mouseY, button, deltaX, deltaY);
		}

		@Override
		public boolean keyPressed(int keyCode, int scanCode, int modifiers) {
			if (this.detailButton.isFocused() && this.detailButton.keyPressed(keyCode, scanCode, modifiers)) {
				return true;
			}

			return this.booleanElement.keyPressed(keyCode, scanCode, modifiers);
		}

		@Override
		public boolean keyReleased(int keyCode, int scanCode, int modifiers) {
			if (this.detailButton.isFocused() && this.detailButton.keyReleased(keyCode, scanCode, modifiers)) {
				return true;
			}

			return this.booleanElement.keyReleased(keyCode, scanCode, modifiers);
		}

		@Override
		public boolean charTyped(char chr, int modifiers) {
			if (this.detailButton.isFocused() && this.detailButton.charTyped(chr, modifiers)) {
				return true;
			}

			return this.booleanElement.charTyped(chr, modifiers);
		}
		*///?}

		//? if >= 1.20.4 {
		@Override
		public boolean mouseScrolled(double mouseX, double mouseY, double horizontalAmount, double verticalAmount) {
			return this.detailButton.mouseScrolled(mouseX, mouseY, horizontalAmount, verticalAmount)
				|| this.booleanElement.mouseScrolled(mouseX, mouseY, horizontalAmount, verticalAmount);
		}
		//?}
	}
}
