const { defineConfig } = require('@vue/cli-service')
module.exports = defineConfig({
  transpileDependencies: true,
   // 基本路径
   publicPath: '/',
   // 输出文件目录
   outputDir: 'dist',
   // 静态资源目录
   assetsDir: 'assets',
   // 是否开启 eslint 保存检测
   lintOnSave: process.env.NODE_ENV !== 'production',
   // 生产环境是否生成 sourceMap 文件
   productionSourceMap: false,
   // 开发服务器配置
   devServer: {
     port: 8080, // 端口号
     open: true, // 启动后是否自动打开浏览器
     proxy: {
       '/api': {
         target: 'http://localhost:3000',
         changeOrigin: true,
         pathRewrite: {
           '^/api': ''
         }
       }
     }
   }

})
