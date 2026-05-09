package com.squinchmods.treeify.common.treeify.ui.control.element;

import com.squinchmods.treeify.common.treeify.ui.control.TreeifyBiomeController;
import dev.isxander.yacl3.api.utils.Dimension;
import dev.isxander.yacl3.gui.YACLScreen;
import dev.isxander.yacl3.gui.controllers.dropdown.AbstractDropdownControllerElement;
import dev.isxander.yacl3.gui.image.impl.ResourceTextureImage;
import net.minecraft.network.chat.Component;
import net.minecraft.resources.Identifier;

import java.util.List;
import java.util.Optional;

//? if >= 26.1 {
import net.minecraft.client.gui.GuiGraphicsExtractor;
//?} else {
/*import net.minecraft.client.gui.GuiGraphics;
*///?}

public final class TreeifyBiomeControllerElement extends AbstractDropdownControllerElement<String, String>
{
	private static final int PREVIEW_SIZE = 16;

	private final TreeifyBiomeController biomeController;

	public TreeifyBiomeControllerElement(TreeifyBiomeController controller, YACLScreen screen, Dimension<Integer> dim) {
		super(controller, screen, dim);
		this.biomeController = controller;
	}

	@Override
	//? if >= 26.1 {
	protected void extractValueText(GuiGraphicsExtractor graphics, int mouseX, int mouseY, float delta)
	//?} else {
	/*protected void drawValueText(GuiGraphics graphics, int mouseX, int mouseY, float delta)
	*///?}
	{
		Dimension<Integer> oldDimension = getDimension();
		setDimension(getDimension().withWidth(getDimension().width() - getDecorationPadding()));
		//? if >= 26.1 {
		super.extractValueText(graphics, mouseX, mouseY, delta);
		//?} else {
		/*super.drawValueText(graphics, mouseX, mouseY, delta);
		*///?}
		setDimension(oldDimension);

		int imageX = getDimension().xLimit() - getXPadding() - getDecorationPadding() + 4;
		int imageY = getDimension().y() + 4;
		renderBiomeImage(this.biomeController.option().pendingValue(), graphics, imageX, imageY, delta);
	}

	@Override
	public List<String> computeMatchingValues() {
		return this.biomeController.searchIds(this.inputField);
	}

	@Override
	public boolean matchingValue(String value) {
		return this.biomeController.searchIds(this.inputField).contains(value) || super.matchingValue(value);
	}

	@Override
	public String getString(String biomeId) {
		return this.biomeController.choice(biomeId)
			.map(choice -> choice.displayName().getString() + " (" + choice.id() + ") ")
			.orElse(biomeId);
	}

	@Override
	protected int getDecorationPadding() {
		return PREVIEW_SIZE;
	}

	@Override
	protected int getDropdownEntryPadding() {
		return 4;
	}

	@Override
	//? if >= 26.1 {
	protected void extractDropdownEntry(GuiGraphicsExtractor graphics, Dimension<Integer> entryDimension, String value)
	//?} else {
	/*protected void renderDropdownEntry(GuiGraphics graphics, Dimension<Integer> entryDimension, String value)
	*///?}
	{
		//? if >= 26.1 {
		super.extractDropdownEntry(graphics, entryDimension, value);
		//?} else {
		/*super.renderDropdownEntry(graphics, entryDimension, value);
		*///?}

		int imageX = entryDimension.xLimit() - 1;
		int imageY = entryDimension.y() + 4;
		renderBiomeImage(value, graphics, imageX, imageY, 1.0F);
	}

	@Override
	protected int getControlWidth() {
		return super.getControlWidth() + getDecorationPadding();
	}

	@Override
	protected Component getValueText() {
		if (this.inputField.isEmpty() || this.biomeController == null) {
			return super.getValueText();
		}

		if (this.inputFieldFocused) {
			return Component.literal(this.inputField);
		}

		return this.biomeController.formatValue();
	}

	private void renderBiomeImage(
		String biomeId,
		//? if >= 26.1 {
		GuiGraphicsExtractor graphics,
		//?} else {
		/*GuiGraphics graphics,
		*///?}
		int x,
		int y,
		float delta
	) {
		Optional<Identifier> previewImage = this.biomeController.choice(biomeId).flatMap(choice -> choice.previewImage());

		if (previewImage.isEmpty()) {
			return;
		}

		try {
			ResourceTextureImage.createFactory(previewImage.get(), 0.0F, 0.0F, PREVIEW_SIZE, PREVIEW_SIZE, PREVIEW_SIZE, PREVIEW_SIZE)
				.prepareImage()
				.completeImage()
				.render(graphics, x, y, 11, delta);
		} catch (Exception ignored) {
		}
	}
}
