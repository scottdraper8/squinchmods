package com.squinchmods.treeify.common.treeify.ui.option;

import dev.isxander.yacl3.api.Option;

public record TreeifyOptionPair<K extends Option<?>, V extends Option<?>>(
	K firstOption,
	V secondOption
)
{
}
