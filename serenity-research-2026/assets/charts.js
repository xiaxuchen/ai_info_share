// assets/charts.js
(function() {
  var style = getComputedStyle(document.documentElement);
  var accent = style.getPropertyValue('--accent').trim();
  var accent2 = style.getPropertyValue('--accent2').trim();
  var ink = style.getPropertyValue('--ink').trim();
  var muted = style.getPropertyValue('--muted').trim();
  var rule = style.getPropertyValue('--rule').trim();
  var bg2 = style.getPropertyValue('--bg2').trim();
  var bg = style.getPropertyValue('--bg').trim();

  // --- Chart 1: Sector Heatmap ---
  var chart1 = echarts.init(document.getElementById('chart-sector-heat'), null, { renderer: 'svg' });
  chart1.setOption({
    animation: false,
    tooltip: {
      trigger: 'item',
      appendToBody: true,
      formatter: function(p) {
        return p.name + '<br/>热度指数: ' + p.value[2] + '<br/>资金: ' + (p.value[3] || '') + '';
      }
    },
    grid: {
      left: '15%',
      right: '10%',
      top: 30,
      bottom: 40
    },
    xAxis: {
      type: 'category',
      data: ['产业确定性', '短期弹性', '资金热度', '政策催化', '机构覆盖'],
      axisLabel: { color: muted, fontSize: 11 },
      axisLine: { lineStyle: { color: rule } },
      axisTick: { show: false },
      splitArea: { show: false }
    },
    yAxis: {
      type: 'category',
      data: ['半导体', 'AI算力', 'PCB/电子材料', '商业航天', '机器人', '新能源', '有色金属'],
      axisLabel: { color: ink, fontSize: 12, fontWeight: 600 },
      axisLine: { lineStyle: { color: rule } },
      axisTick: { show: false },
      splitArea: { show: false }
    },
    visualMap: {
      min: 1,
      max: 10,
      calculable: false,
      orient: 'horizontal',
      left: 'center',
      bottom: 0,
      inRange: { color: [bg2, accent2, accent] },
      textStyle: { color: muted, fontSize: 10 }
    },
    series: [{
      type: 'heatmap',
      data: [
        [0, 0, 9], [1, 0, 9], [2, 0, 9], [3, 0, 8], [4, 0, 9],
        [0, 1, 10], [1, 1, 9], [2, 1, 8], [3, 1, 7], [4, 1, 9],
        [0, 2, 7], [1, 2, 10], [2, 2, 9], [3, 2, 6], [4, 2, 6],
        [0, 3, 5], [1, 3, 10], [2, 3, 10], [3, 3, 10], [4, 3, 5],
        [0, 4, 7], [1, 4, 8], [2, 4, 7], [3, 4, 9], [4, 4, 7],
        [0, 5, 6], [1, 5, 6], [2, 5, 5], [3, 5, 6], [4, 5, 7],
        [0, 6, 7], [1, 6, 7], [2, 6, 7], [3, 6, 5], [4, 6, 5]
      ],
      label: {
        show: true,
        color: function(p) { return p.value[2] >= 8 ? bg : ink; },
        fontSize: 12,
        fontWeight: 600
      },
      emphasis: {
        itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0,0,0,0.5)' }
      }
    }]
  });
  window.addEventListener('resize', function() { chart1.resize(); });

  // --- Chart 2: MA5 Breakout Distribution ---
  var chart2 = echarts.init(document.getElementById('chart-ma5-dist'), null, { renderer: 'svg' });
  chart2.setOption({
    animation: false,
    tooltip: {
      trigger: 'axis',
      appendToBody: true,
      axisPointer: { type: 'shadow' }
    },
    grid: {
      left: '12%',
      right: '8%',
      top: 16,
      bottom: 30
    },
    xAxis: {
      type: 'value',
      axisLabel: { color: muted, fontSize: 11 },
      axisLine: { lineStyle: { color: rule } },
      splitLine: { lineStyle: { color: rule } }
    },
    yAxis: {
      type: 'category',
      data: ['商业航天', '有色金属', '新能源', '机器人', 'AI算力+PCB', '半导体'],
      axisLabel: { color: ink, fontSize: 12 },
      axisLine: { lineStyle: { color: rule } },
      axisTick: { show: false }
    },
    series: [{
      type: 'bar',
      data: [
        { value: 5, itemStyle: { color: accent2 } },
        { value: 4, itemStyle: { color: accent2 } },
        { value: 3, itemStyle: { color: accent } },
        { value: 3, itemStyle: { color: accent } },
        { value: 6, itemStyle: { color: accent } },
        { value: 7, itemStyle: { color: accent } }
      ],
      label: {
        show: true,
        position: 'right',
        color: ink,
        fontSize: 12,
        fontWeight: 600
      },
      barWidth: 22
    }]
  });
  window.addEventListener('resize', function() { chart2.resize(); });

})();