/** @wdoo-module **/

export const session = wdoo.__session_info__ || {};
delete wdoo.__session_info__;
