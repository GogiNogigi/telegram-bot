{ pkgs }: {
  deps = [
    pkgs.python311
    pkgs.openssl
    pkgs.postgresql
  ];
}