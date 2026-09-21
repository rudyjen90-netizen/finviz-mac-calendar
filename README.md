# Finviz 美股经济日历 → Mac / iPhone

这套免费工具每 6 小时读取一次 Finviz 美国经济日历，生成 Apple 日历可以订阅的 `finviz-economic.ics`。它不只是提醒数据时间，也是一套结合真实市场事件学习的美股新手训练日历。

默认设置：

- 只保留 Finviz `importance = 2/3` 的中、高影响事件
- 高影响显示为 🔴，中影响显示为 🟠
- 日历标题优先使用中文；只有没有合适中文名称时才保留必要英文
- 事件备注增加“新手解释 / 为什么重要 / 数据对比 / 情景判断 / 市场传导链 / 重点观察”
- 每个交易日安排一张不重复的“今日学习卡”，同一天的事件共用当天课程，避免重复刷屏
- 每个事件附三道公布后复盘题，训练从数据、利率和指数反应中独立判断
- 事件类别尽量显示为中文
- 事件前 30 分钟提醒
- Finviz 的美国东部时间转换成 UTC；Mac/iPhone 会自动显示为维也纳或设备当前时区
- 设备时区说明只在这里统一说明，不再重复写进每一个日历事件
- 抓取失败时工作流停止，不会用空白文件覆盖上一份有效日历

## 8 周训练路线

课程从 2026 年 9 月 21 日开始，每周一个阶段、每个交易日一课，完成后自动循环巩固：

1. 看懂经济日历：公布值、预测值、前值、修正值与预期差
2. 理解美联储：双重目标、利率传导、鹰派与鸽派、点阵图
3. 读懂美债与利率：2年期、10年期、实际利率与收益率曲线
4. 理解通胀：CPI、核心通胀、PCE、PPI与黏性服务通胀
5. 理解就业：非农、失业率、工资、JOLTS、ADP与初请失业金
6. 理解经济增长：GDP、PMI、零售销售、房地产与领先指标
7. 理解市场反应：好数据为什么会跌、跨市场确认、利好兑现
8. 建立交易纪律：催化剂、风险收益比、仓位、假突破与复盘

训练重点不是死背结论，而是逐渐形成这条思维链：

> 发生了什么 → 市场原来预期什么 → 出现了多大预期差 → 美债和美元怎么反应 → QQQ/SPY是否确认 → 哪些行业最敏感

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
