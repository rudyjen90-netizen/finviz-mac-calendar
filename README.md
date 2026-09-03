# Finviz 美股经济日历 → Mac / iPhone

这套免费工具每 6 小时读取一次 Finviz 美国经济日历，生成 Apple 日历可以订阅的 `finviz-economic.ics`。

默认设置：

- 只保留 Finviz `importance = 2/3` 的中、高影响事件
- 高影响显示为 🔴，中影响显示为 🟠
- 常见大事件附中文名称
- 事件前 30 分钟提醒
- Finviz 的美国东部时间转换成 UTC；Mac/iPhone 会自动显示为维也纳或设备当前时区
- 抓取失败时工作流停止，不会用空白文件覆盖上一份有效日历

## 第一次设置（约 5–10 分钟）

1. 登录 GitHub，新建一个 **Public** 仓库，名称建议 `finviz-mac-calendar`。不要添加 README 或其他初始化文件。
2. 在 Mac 的“终端”中进入解压后的文件夹，依次运行：

   ```bash
   git init
   git add .
   git commit -m "Create Finviz calendar"
   git branch -M main
   git remote add origin https://github.com/你的GitHub用户名/finviz-mac-calendar.git
   git push -u origin main
   ```

3. 打开仓库的 **Actions** 页面，选择 **Update economic calendar**，点击 **Run workflow**。第一次运行完成后，`docs/finviz-economic.ics` 会自动生成。
4. 打开 **Settings → Pages**，在 **Build and deployment → Source** 中选择 **GitHub Actions**。
5. 回到 **Actions → Update economic calendar → Run workflow** 手动运行一次，等待绿色对勾。你的固定订阅地址将是：

   ```text
   https://你的GitHub用户名.github.io/finviz-mac-calendar/finviz-economic.ics
   ```

## 添加到 Mac 和 iPhone

1. Mac 打开“日历”。
2. 选择 **文件 → 新建日历订阅**。
3. 粘贴上面的 `.ics` 地址并点击“订阅”。
4. 名称填写 `美股经济日历`；位置选择 **iCloud**；自动刷新选择 **每小时**。
5. 不要勾选“移除提醒”或“忽略提醒”，否则提前 30 分钟提醒不会出现。

选择 iCloud 后，日历会同步到使用同一 Apple 账户的 iPhone。

## 个性化设置

在 `.github/workflows/update-calendar.yml` 的这一行：

```yaml
run: python finviz_calendar.py
```

可以改为：

```yaml
run: python finviz_calendar.py --min-importance 3 --reminder-minutes 60
```

- `--min-importance 3`：只显示高影响事件
- `--min-importance 2`：显示中、高影响事件（默认）
- `--reminder-minutes 60`：提前 60 分钟提醒
- `--weeks-ahead 4`：抓取未来四周（默认）

## 重要说明

这是非官方的个人用途转换器，不是 Finviz 官方产品。Finviz 若修改接口或访问规则，自动更新可能失败；GitHub 会在 Actions 页面显示失败记录，而上一份已生成日历仍会保留。请遵守 Finviz 的使用条款，不要把更新频率提高到不合理的程度。
