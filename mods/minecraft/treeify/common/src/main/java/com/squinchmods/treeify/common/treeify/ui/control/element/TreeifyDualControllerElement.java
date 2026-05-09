package com.squinchmods.treeify.common.treeify.ui.control.element;

import dev.isxander.yacl3.api.utils.Dimension;
import dev.isxander.yacl3.gui.AbstractWidget;
import dev.isxander.yacl3.gui.TextScaledButtonWidget;
import net.minecraft.client.gui.narration.NarrationElementOutput;
import org.jetbrains.annotations.Nullable;

//? if >=1.21.9 {
import net.minecraft.client.input.CharacterEvent;
import net.minecraft.client.input.KeyEvent;
import net.minecraft.client.input.MouseButtonEvent;
//?}

//? if >= 26.1 {
import net.minecraft.client.gui.GuiGraphicsExtractor;
//?} else {
/*import net.minecraft.client.gui.GuiGraphics;
*///?}

public final class TreeifyDualControllerElement extends AbstractWidget
{
	private final AbstractWidget firstElement;
	private final AbstractWidget secondElement;
	@Nullable
	private final TextScaledButtonWidget resetButton;
	private boolean focused;

	public TreeifyDualControllerElement(
		Dimension<Integer> dim,
		AbstractWidget firstElement,
		AbstractWidget secondElement,
		@Nullable TextScaledButtonWidget resetButton
	) {
		super(dim);

		this.firstElement = firstElement;
		this.secondElement = secondElement;
		this.resetButton = resetButton;
	}

	@Override
	public void mouseMoved(double mouseX, double mouseY) {
		this.firstElement.mouseMoved(mouseX, mouseY);
		this.secondElement.mouseMoved(mouseX, mouseY);

		if (this.resetButton != null) {
			this.resetButton.mouseMoved(mouseX, mouseY);
		}
	}

	//? if >=1.21.9 {
	@Override
	public boolean mouseClicked(MouseButtonEvent mouseButtonEvent, boolean doubleClick) {
		this.firstElement.setFocused(false);
		this.secondElement.setFocused(false);

		if (this.firstElement.mouseClicked(mouseButtonEvent, doubleClick)) {
			this.firstElement.setFocused(true);
			this.focused = true;
			return true;
		}

		if (this.secondElement.mouseClicked(mouseButtonEvent, doubleClick)) {
			this.secondElement.setFocused(true);
			this.focused = true;
			return true;
		}

		boolean handledByReset = this.resetButton != null && this.resetButton.mouseClicked(mouseButtonEvent, doubleClick);
		this.focused = handledByReset;
		return handledByReset;
	}

	@Override
	public boolean mouseReleased(MouseButtonEvent mouseButtonEvent) {
		return this.firstElement.mouseReleased(mouseButtonEvent)
			|| this.secondElement.mouseReleased(mouseButtonEvent)
			|| (this.resetButton != null && this.resetButton.mouseReleased(mouseButtonEvent));
	}

	@Override
	public boolean mouseDragged(MouseButtonEvent mouseButtonEvent, double dx, double dy) {
		return this.firstElement.mouseDragged(mouseButtonEvent, dx, dy)
			|| this.secondElement.mouseDragged(mouseButtonEvent, dx, dy)
			|| (this.resetButton != null && this.resetButton.mouseDragged(mouseButtonEvent, dx, dy));
	}

	@Override
	public boolean keyPressed(KeyEvent keyEvent) {
		return this.firstElement.keyPressed(keyEvent)
			|| this.secondElement.keyPressed(keyEvent)
			|| (this.resetButton != null && this.resetButton.keyPressed(keyEvent));
	}

	@Override
	public boolean keyReleased(KeyEvent keyEvent) {
		return this.firstElement.keyReleased(keyEvent)
			|| this.secondElement.keyReleased(keyEvent)
			|| (this.resetButton != null && this.resetButton.keyReleased(keyEvent));
	}

	@Override
	public boolean charTyped(CharacterEvent characterEvent) {
		return this.firstElement.charTyped(characterEvent)
			|| this.secondElement.charTyped(characterEvent)
			|| (this.resetButton != null && this.resetButton.charTyped(characterEvent));
	}
	//?} else {
	/*@Override
	public boolean mouseClicked(double mouseX, double mouseY, int button) {
		this.firstElement.setFocused(false);
		this.secondElement.setFocused(false);

		if (this.firstElement.mouseClicked(mouseX, mouseY, button)) {
			this.firstElement.setFocused(true);
			this.focused = true;
			return true;
		}

		if (this.secondElement.mouseClicked(mouseX, mouseY, button)) {
			this.secondElement.setFocused(true);
			this.focused = true;
			return true;
		}

		boolean handledByReset = this.resetButton != null && this.resetButton.mouseClicked(mouseX, mouseY, button);
		this.focused = handledByReset;
		return handledByReset;
	}

	@Override
	public boolean mouseReleased(double mouseX, double mouseY, int button) {
		return this.firstElement.mouseReleased(mouseX, mouseY, button)
			|| this.secondElement.mouseReleased(mouseX, mouseY, button)
			|| (this.resetButton != null && this.resetButton.mouseReleased(mouseX, mouseY, button));
	}

	@Override
	public boolean mouseDragged(double mouseX, double mouseY, int button, double deltaX, double deltaY) {
		return this.firstElement.mouseDragged(mouseX, mouseY, button, deltaX, deltaY)
			|| this.secondElement.mouseDragged(mouseX, mouseY, button, deltaX, deltaY)
			|| (this.resetButton != null && this.resetButton.mouseDragged(mouseX, mouseY, button, deltaX, deltaY));
	}

	@Override
	public boolean keyPressed(int keyCode, int scanCode, int modifiers) {
		return this.firstElement.keyPressed(keyCode, scanCode, modifiers)
			|| this.secondElement.keyPressed(keyCode, scanCode, modifiers)
			|| (this.resetButton != null && this.resetButton.keyPressed(keyCode, scanCode, modifiers));
	}

	@Override
	public boolean keyReleased(int keyCode, int scanCode, int modifiers) {
		return this.firstElement.keyReleased(keyCode, scanCode, modifiers)
			|| this.secondElement.keyReleased(keyCode, scanCode, modifiers)
			|| (this.resetButton != null && this.resetButton.keyReleased(keyCode, scanCode, modifiers));
	}

	@Override
	public boolean charTyped(char chr, int modifiers) {
		return this.firstElement.charTyped(chr, modifiers)
			|| this.secondElement.charTyped(chr, modifiers)
			|| (this.resetButton != null && this.resetButton.charTyped(chr, modifiers));
	}
	*///?}

	//? if >=1.20.4 {
	@Override
	public boolean mouseScrolled(double mouseX, double mouseY, double horizontalAmount, double verticalAmount) {
		return this.firstElement.mouseScrolled(mouseX, mouseY, horizontalAmount, verticalAmount)
			|| this.secondElement.mouseScrolled(mouseX, mouseY, horizontalAmount, verticalAmount)
			|| (this.resetButton != null && this.resetButton.mouseScrolled(mouseX, mouseY, horizontalAmount, verticalAmount));
	}
	//?}

	@Override
	public void setFocused(boolean focused) {
		this.focused = focused;

		if (!focused) {
			this.firstElement.setFocused(false);
			this.secondElement.setFocused(false);

			if (this.resetButton != null) {
				this.resetButton.setFocused(false);
			}
		}
	}

	@Override
	public boolean isFocused() {
		return this.focused
			|| this.firstElement.isFocused()
			|| this.secondElement.isFocused()
			|| (this.resetButton != null && this.resetButton.isFocused());
	}

	@Override
	public void setDimension(Dimension<Integer> dim) {
		Dimension<Integer> firstElementDimension = dim
			.moved(0, 0)
			.withWidth(this.firstElement.getDimension().width())
			.withHeight(this.firstElement.getDimension().height());
		Dimension<Integer> secondElementDimension = dim
			.moved(this.firstElement.getDimension().width(), 0)
			.withWidth(this.secondElement.getDimension().width())
			.withHeight(this.secondElement.getDimension().height());

		this.firstElement.setDimension(firstElementDimension);
		this.secondElement.setDimension(secondElementDimension);

		if (this.resetButton != null) {
			this.resetButton.setY(dim.y());
		}

		super.setDimension(dim);
	}

	@Override
	public void unfocus() {
		this.focused = false;
		this.firstElement.unfocus();
		this.secondElement.unfocus();

		if (this.resetButton != null) {
			this.resetButton.setFocused(false);
		}

		super.unfocus();
	}

	//? if >= 21.6 {
	@Override
	public void extractRenderState(GuiGraphicsExtractor graphics, int mouseX, int mouseY, float tickDelta) {
		this.firstElement.extractRenderState(graphics, mouseX, mouseY, tickDelta);
		this.secondElement.extractRenderState(graphics, mouseX, mouseY, tickDelta);

		if (this.resetButton != null) {
			this.resetButton.setY(getDimension().y());
			this.resetButton.extractRenderState(graphics, mouseX, mouseY, tickDelta);
		}
	}
	//?} else {
	/*@Override
	public void render(GuiGraphics graphics, int mouseX, int mouseY, float tickDelta) {
		this.firstElement.render(graphics, mouseX, mouseY, tickDelta);
		this.secondElement.render(graphics, mouseX, mouseY, tickDelta);

		if (this.resetButton != null) {
			this.resetButton.setY(getDimension().y());
			this.resetButton.render(graphics, mouseX, mouseY, tickDelta);
		}
	}
	*///?}

	@Override
	public NarrationPriority narrationPriority() {
		return NarrationPriority.NONE;
	}

	@Override
	public boolean matchesSearch(String query) {
		return this.firstElement.matchesSearch(query) || this.secondElement.matchesSearch(query);
	}

	@Override
	public void updateNarration(NarrationElementOutput builder) {
		this.firstElement.updateNarration(builder);
		this.secondElement.updateNarration(builder);
	}
}
