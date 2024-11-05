self: {
  lib,
  config,
  pkgs,
  ...
}:

with lib;

let 
  cfg = config.services.auto-add-torrents;
in {
  options = {
    services.auto-add-torrents = {
      enable = mkEnableOption "auto-add-torrents";

      configFile = mkOption {
        type = types.path;
        description = "The path to the config file";
      };

      logDir = mkOption {
        type = types.path;
        description = "The directory in which a logs folder will be created";
        default = "/var/log/auto-add-torrents/";
      };

      package = mkOption {
        type = types.package;
        default = self.packages.x86_64-linux.default;
        description = "The package to use";
      };

      user = mkOption {
        type = types.str;
        default = "auto-add-torrents";
        description = "User to run as";
      };

      group = mkOption {
        type = types.str;
        default = "auto-add-torrents";
        description = "Group to run as";
      };    
    };
  };

  config = mkIf cfg.enable {
    systemd.services.auto-add-torrents = {
      description = "Automatically add torrents";
      wantedBy = [ "multi-user.target" ];
      serviceConfig = {
        ExecStart = "${cfg.package}/bin/auto-add-torrents -l ${cfg.logDir} -c ${cfg.configFile}";
        Restart = "on-failure";
        User = cfg.user;
        Group = cfg.group;
        LogsDirectory = "auto-add-torrents";
      };
    };

    users = mkIf (cfg.user == "auto-add-torrents"){
      users.auto-add-torrents = {
        isSystemUser = true;
        group = "auto-add-torrents";
      };

      groups.auto-add-torrents = {};
    };
  };
}
