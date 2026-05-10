package com.squinchmods.vegetate.common.vegetate.ui.shell;

import com.squinchmods.vegetate.common.vegetate.ui.service.ConfigUiCatalogService;
import com.squinchmods.vegetate.common.vegetate.ui.service.ConfigUiEditService;
import com.squinchmods.vegetate.common.vegetate.ui.service.ConfigUiSaveService;
import com.squinchmods.vegetate.common.vegetate.ui.service.VegetateConfigSession;
import java.util.Objects;

public record VegetateConfigScreenContext(
    ConfigUiCatalogService catalogService,
    ConfigUiEditService editService,
    ConfigUiSaveService saveService,
    VegetateConfigSession session) {
  public VegetateConfigScreenContext {
    Objects.requireNonNull(catalogService, "catalogService cannot be null");
    Objects.requireNonNull(editService, "editService cannot be null");
    Objects.requireNonNull(saveService, "saveService cannot be null");
    Objects.requireNonNull(session, "session cannot be null");
  }
}
