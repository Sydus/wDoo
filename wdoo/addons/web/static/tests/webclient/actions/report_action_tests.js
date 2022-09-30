/** @wdoo-module **/

import { registry } from "@web/core/registry";
import { uiService } from "@web/core/ui/ui_service";
import testUtils from "web.test_utils";
import ReportClientAction from "report.client_action";
import { makeFakeNotificationService } from "../../helpers/mock_services";
import { patchWithCleanup, click } from "../../helpers/utils";
import { createWebClient, doAction, getActionManagerServerData } from "./../helpers";
import { mockDownload } from "@web/../tests/helpers/utils";
import { clearRegistryWithCleanup } from "../../helpers/mock_env";
import { session } from "@web/session";

let serverData;

const serviceRegistry = registry.category("services");

QUnit.module("ActionManager", (hooks) => {
    hooks.beforeEach(() => {
        serverData = getActionManagerServerData();
        clearRegistryWithCleanup(registry.category("main_components"));
    });

});
