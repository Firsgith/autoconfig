name: Generate OpenWrt Config

on:
  push:
    branches:
      - main  # 触发条件：推送到 main 分支

jobs:
  generate-config:
    runs-on: ubuntu-latest

    env:
      OPENWRT_REPO: https://github.com/coolsnowwolf/lede.git  # 默认 OpenWrt 仓库
      OPENWRT_BRANCH: master  # 默认分支
      OPENWRT_SRC: ${{ github.workspace }}/openwrt  # 克隆到子目录！！！

    steps:
      # 克隆当前仓库
      - name: Checkout repository
        uses: actions/checkout@v3

      # 克隆 OpenWrt 源码到子目录
      - name: Clone OpenWrt source code
        run: |
          rm -rf ${{ env.OPENWRT_SRC }}
          mkdir -p ${{ env.OPENWRT_SRC }}
          git clone ${{ env.OPENWRT_REPO }} ${{ env.OPENWRT_SRC }}
          cd ${{ env.OPENWRT_SRC }}
          git checkout ${{ env.OPENWRT_BRANCH }}

      # 更新 Feeds
      - name: Update and install feeds
        run: |
          cd ${{ env.OPENWRT_SRC }}
          ./scripts/feeds update -a
          ./scripts/feeds install -a

      # 安装 Python 和 Kconfiglib
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.9'

      - name: Install Kconfiglib
        run: |
          pip install kconfiglib

      # 运行生成配置的脚本
      - name: Run configuration script
        run: |
          python ${{ github.workspace }}/generate_config.py
        env:
          OPENWRT_SRC: ${{ env.OPENWRT_SRC }}

      # 运行 make oldconfig 确保配置完整
      - name: Run make oldconfig
        run: |
          cd ${{ env.OPENWRT_SRC }}
          make oldconfig -y

      # 读取 packages 文件并设置步骤输出
      - name: Read packages file for validation
        id: read-packages
        run: |
          PACKAGES=$(cat packages | grep -v '^#' | grep -v '^$' | sed 's/^/CONFIG_PACKAGE_/')
          echo "::set-output name=package_list::$PACKAGES"

      # 验证生成的 .config 文件
      - name: Validate generated .config
        run: |
          # 定义验证函数
          validate_config() {
            local missing_packages=""
            cd ${{ env.OPENWRT_SRC }}

            # 遍历所有目标包
            for package in $1; do
              if ! grep -q "$package=y" .config; then
                missing_packages+="$package "
              fi
            done

            # 如果有缺失的包，输出错误信息并退出
            if [ -n "$missing_packages" ]; then
              echo "Error: The following packages are missing in .config:"
              echo "$missing_packages"
              exit 1
            else
              echo ".config file validated successfully."
            fi
          }

          # 调用验证函数
          validate_config "${{ steps.read-packages.outputs.package_list }}"
