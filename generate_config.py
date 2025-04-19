from kconfiglib import Kconfig
import os
import sys
import subprocess
import logging
from concurrent.futures import ThreadPoolExecutor
import glob

# 配置日志记录
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)

# 设置 OpenWrt 源代码根目录 (直接从环境变量获取)
OPENWRT_SRC = os.environ.get("OPENWRT_SRC")
if not OPENWRT_SRC:
    logging.error("Error: OPENWRT_SRC environment variable not set.")
    sys.exit(1)

logging.info(f"OPENWRT_SRC is set to: {OPENWRT_SRC}")

# 初始化 Kconfig 对象，指定源代码根目录
kconfig_path = os.path.join(OPENWRT_SRC, "Kconfig")  # 默认路径
if not os.path.isfile(kconfig_path):
    # 尝试查找 Kconfig 文件的实际路径
    possible_paths = glob.glob(os.path.join(OPENWRT_SRC, "**", "Kconfig"), recursive=True)
    if not possible_paths:
        logging.error(f"Error: Kconfig file not found in '{OPENWRT_SRC}' or its subdirectories.")
        sys.exit(1)
    kconfig_path = possible_paths[0]  # 使用找到的第一个路径

logging.info(f"Loading Kconfig file from: {kconfig_path}")
kconf = Kconfig(kconfig_path)

# 用于跟踪已启用的依赖项，避免重复处理
enabled_dependencies = set()

# 从 packages 文件读取目标软件包列表
def read_packages_file():
    packages_file = "packages"
    if not os.path.isfile(packages_file):
        logging.error(f"Error: The file '{packages_file}' does not exist.")
        sys.exit(1)

    target_config_vars = []
    with open(packages_file, "r") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                logging.info(f"Skipping empty line {line_num} in '{packages_file}'.")
                continue
            if line.startswith("#"):
                logging.info(f"Skipping comment line {line_num}: '{line}' in '{packages_file}'.")
                continue
            if any(char.isspace() for char in line):
                logging.error(f"Error: Invalid package name '{line}' on line {line_num}. Package names cannot contain spaces.")
                sys.exit(1)
            if not line.startswith("CONFIG_PACKAGE_"):
                config_var = "CONFIG_PACKAGE_" + line
                logging.info(f"Adding prefix 'CONFIG_PACKAGE_' to line {line_num}: '{line}' -> '{config_var}'.")
                target_config_vars.append(config_var)
            else:
                target_config_vars.append(line)

    if not target_config_vars:
        logging.error("Error: No valid package names found in 'packages' file.")
        sys.exit(1)

    return target_config_vars

target_config_vars = read_packages_file()

# 递归地启用依赖项，避免重复处理
def enable_dependencies(symbol):
    if symbol is None or symbol.name in enabled_dependencies:
        return

    enabled_dependencies.add(symbol.name)

    for dep in symbol.all_depends():
        if dep.type in (Kconfig.BOOLEAN, Kconfig.TRISTATE) and dep.str_value == 'n':
            logging.info(f"Enabling dependency: {dep.name}")
            dep.set_value(2)
            enable_dependencies(dep)

# 检测冲突
def check_conflicts(symbol):
    if symbol is None or symbol.str_value != 'y':
        return

    # 检查 imply ! 冲突
    for imp in symbol.implies:
        if imp.negated:
            conflicting_sym = imp.expr.symbol
            if conflicting_sym and conflicting_sym.str_value == 'y':
                logging.warning(f"Conflict: {symbol.name} implies disabling {conflicting_sym.name}.")

    # 检查互斥关系（reverse_deps）
    for reverse_dep in symbol.direct_reverse_deps:
        if reverse_dep.str_value == 'y':
            logging.warning(f"Conflict: {symbol.name} conflicts with {reverse_dep.name}.")

    # 检查 choice 组冲突
    if symbol.choice and symbol.choice.selection != symbol:
        logging.warning(f"Conflict detected: {symbol.name} is part of a choice group and conflicts with the current selection.")

# 启用目标软件包并处理依赖和冲突
for config_var in target_config_vars:
    symbol = kconf.syms.get(config_var)
    if symbol is None:
        logging.error(f"Error: Config variable {config_var} not found!")
        sys.exit(1)

    if symbol.choice and symbol.choice.selection != symbol:
        logging.warning(f"Conflict detected: {symbol.name} is part of a choice group.")
        continue

    symbol.set_value(2)
    enable_dependencies(symbol)
    check_conflicts(symbol)

# 同步所有配置
kconf.sync_all()

# 加载现有配置（如果存在）
try:
    kconf.load_config(os.path.join(OPENWRT_SRC, ".config"))
except FileNotFoundError:
    pass

# 写入新的 .config 文件
kconf.write_config(os.path.join(OPENWRT_SRC, ".config"))
logging.info("Generated .config file successfully.")

# 运行 make oldconfig 确保配置完整
def run_make_oldconfig():
    try:
        logging.info("Running 'make oldconfig' to finalize configuration...")
        subprocess.run(["make", "oldconfig", "-y"], cwd=OPENWRT_SRC, check=True)
        logging.info("'make oldconfig' completed successfully.")
    except subprocess.CalledProcessError as e:
        logging.error(f"Error running 'make oldconfig': {e}")
        sys.exit(1)

run_make_oldconfig()
