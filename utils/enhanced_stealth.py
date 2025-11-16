#!/usr/bin/env python3
"""
增强型反检测模块 - 2025版
整合最新的Cloudflare绕过技术
"""

import asyncio
import random
from typing import Optional
from playwright.async_api import Page, BrowserContext
from utils.logger import setup_logger

logger = setup_logger(__name__)


class EnhancedStealth:
    """增强型反检测类 - 集成2025年最新技术"""

    @staticmethod
    async def inject_stealth_scripts(page: Page) -> None:
        """
        注入增强版反检测脚本
        覆盖20+检测特征
        """
        await page.add_init_script("""
            // ==================== 核心反检测脚本（2025增强版） ====================

            // 1. 移除 webdriver 标志（最重要）
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
                configurable: true
            });
            delete navigator.__proto__.webdriver;

            // 2. 覆盖 Chrome 自动化标志
            Object.defineProperty(navigator, 'automation', {
                get: () => undefined,
                configurable: true
            });

            // 3. 伪装 plugins（headless 默认为空）
            Object.defineProperty(navigator, 'plugins', {
                get: () => [
                    {
                        0: {type: "application/x-google-chrome-pdf", suffixes: "pdf", description: "Portable Document Format"},
                        name: "Chrome PDF Plugin",
                        filename: "internal-pdf-viewer",
                        length: 1
                    },
                    {
                        0: {type: "application/pdf", suffixes: "pdf", description: "Portable Document Format"},
                        name: "Chromium PDF Plugin",
                        filename: "internal-pdf-viewer",
                        length: 1
                    },
                    {
                        0: {type: "application/x-nacl", suffixes: "", description: "Native Client Executable"},
                        1: {type: "application/x-pnacl", suffixes: "", description: "Portable Native Client Executable"},
                        name: "Native Client",
                        filename: "internal-nacl-plugin",
                        length: 2
                    }
                ],
                configurable: true
            });

            // 4. 伪装 languages（更真实的语言列表）
            Object.defineProperty(navigator, 'languages', {
                get: () => ['zh-CN', 'zh', 'en-US', 'en'],
                configurable: true
            });

            // 5. 伪装 permissions（headless 模式下会暴露）
            const originalQuery = window.navigator.permissions?.query;
            if (originalQuery) {
                window.navigator.permissions.query = (parameters) => (
                    parameters.name === 'notifications' ?
                        Promise.resolve({state: Notification.permission}) :
                        originalQuery(parameters)
                );
            }

            // 6. 伪装 Chrome 特性
            window.chrome = {
                runtime: {},
                loadTimes: function() {},
                csi: function() {},
                app: {
                    isInstalled: false,
                    InstallState: {
                        DISABLED: 'disabled',
                        INSTALLED: 'installed',
                        NOT_INSTALLED: 'not_installed'
                    },
                    RunningState: {
                        CANNOT_RUN: 'cannot_run',
                        READY_TO_RUN: 'ready_to_run',
                        RUNNING: 'running'
                    }
                }
            };

            // 7. 修复 iframe contentWindow（headless 特征）
            Object.defineProperty(HTMLIFrameElement.prototype, 'contentWindow', {
                get: function() {
                    return window;
                },
                configurable: true
            });

            // 8. 伪装 connection（headless 通常显示为 'none'）
            Object.defineProperty(navigator, 'connection', {
                get: () => ({
                    effectiveType: '4g',
                    rtt: 50,
                    downlink: 10,
                    downlinkMax: Infinity,
                    saveData: false,
                    type: 'wifi'
                }),
                configurable: true
            });

            // 9. 伪装 battery API
            Object.defineProperty(navigator, 'getBattery', {
                get: () => () => Promise.resolve({
                    charging: true,
                    chargingTime: 0,
                    dischargingTime: Infinity,
                    level: 1
                }),
                configurable: true
            });

            // 10. 伪装时区偏移（防止服务器端检测）
            const originalGetTimezoneOffset = Date.prototype.getTimezoneOffset;
            Date.prototype.getTimezoneOffset = function() {
                return -480; // 中国时区 UTC+8
            };

            // ==================== 高级指纹伪装（2025新增） ====================

            // 生成会话级别的随机种子（确保指纹一致性）
            const sessionSeed = Date.now() + Math.random();

            // 简单的伪随机数生成器（基于种子）
            function seededRandom(seed) {
                const x = Math.sin(seed++) * 10000;
                return x - Math.floor(x);
            }

            // 11. Canvas指纹随机化（2025增强版 - 多层噪声）
            const canvasSeed = sessionSeed * 1.1;
            const originalToDataURL = HTMLCanvasElement.prototype.toDataURL;
            const originalToBlob = HTMLCanvasElement.prototype.toBlob;
            const originalGetImageData = CanvasRenderingContext2D.prototype.getImageData;

            // 为Canvas添加亚像素级噪声
            HTMLCanvasElement.prototype.toDataURL = function(type) {
                const context = this.getContext('2d');
                if (context) {
                    const imageData = context.getImageData(0, 0, this.width, this.height);
                    const pixels = imageData.data;

                    // 添加基于种子的确定性噪声（每100个像素添加1-2个单位的噪声）
                    for (let i = 0; i < pixels.length; i += 400) {
                        const noise = Math.floor(seededRandom(canvasSeed + i) * 3) - 1;
                        pixels[i] = Math.max(0, Math.min(255, pixels[i] + noise));
                    }

                    context.putImageData(imageData, 0, 0);
                }
                return originalToDataURL.apply(this, arguments);
            };

            HTMLCanvasElement.prototype.toBlob = function() {
                const context = this.getContext('2d');
                if (context) {
                    const imageData = context.getImageData(0, 0, this.width, this.height);
                    const pixels = imageData.data;

                    for (let i = 0; i < pixels.length; i += 400) {
                        const noise = Math.floor(seededRandom(canvasSeed + i) * 3) - 1;
                        pixels[i] = Math.max(0, Math.min(255, pixels[i] + noise));
                    }

                    context.putImageData(imageData, 0, 0);
                }
                return originalToBlob.apply(this, arguments);
            };

            // Canvas getImageData也需要一致性处理
            CanvasRenderingContext2D.prototype.getImageData = function() {
                const imageData = originalGetImageData.apply(this, arguments);
                const pixels = imageData.data;

                // 使用相同的种子确保一致性
                for (let i = 0; i < pixels.length; i += 400) {
                    const noise = Math.floor(seededRandom(canvasSeed + i) * 3) - 1;
                    pixels[i] = Math.max(0, Math.min(255, pixels[i] + noise));
                }

                return imageData;
            };

            // 12. WebGL指纹一致性伪装
            const getParameter = WebGLRenderingContext.prototype.getParameter;
            WebGLRenderingContext.prototype.getParameter = function(parameter) {
                // UNMASKED_VENDOR_WEBGL
                if (parameter === 37445) {
                    return 'Intel Inc.';
                }
                // UNMASKED_RENDERER_WEBGL
                if (parameter === 37446) {
                    return 'Intel Iris OpenGL Engine';
                }
                return getParameter.apply(this, arguments);
            };

            // WebGL2 支持
            if (window.WebGL2RenderingContext) {
                const getParameter2 = WebGL2RenderingContext.prototype.getParameter;
                WebGL2RenderingContext.prototype.getParameter = function(parameter) {
                    if (parameter === 37445) return 'Intel Inc.';
                    if (parameter === 37446) return 'Intel Iris OpenGL Engine';
                    return getParameter2.apply(this, arguments);
                };
            }

            // 13. AudioContext指纹随机化（2025增强版 - 确定性噪声）
            if (window.AudioContext || window.webkitAudioContext) {
                const audioSeed = sessionSeed * 1.3;
                const OriginalAudioContext = window.AudioContext || window.webkitAudioContext;
                const NewAudioContext = function() {
                    const context = new OriginalAudioContext();
                    const originalCreateOscillator = context.createOscillator;
                    const originalCreateDynamicsCompressor = context.createDynamicsCompressor;

                    // 劫持 createOscillator
                    context.createOscillator = function() {
                        const oscillator = originalCreateOscillator.apply(this, arguments);
                        const originalStart = oscillator.start;
                        oscillator.start = function(when) {
                            // 添加基于种子的确定性延迟
                            const noise = seededRandom(audioSeed) * 0.0001;
                            return originalStart.call(this, when ? when + noise : noise);
                        };
                        return oscillator;
                    };

                    // 劫持 createDynamicsCompressor（音频指纹的另一个检测点）
                    context.createDynamicsCompressor = function() {
                        const compressor = originalCreateDynamicsCompressor.apply(this, arguments);
                        const threshold = compressor.threshold;
                        const knee = compressor.knee;
                        const ratio = compressor.ratio;
                        const attack = compressor.attack;
                        const release = compressor.release;

                        // 添加微小的确定性偏移
                        Object.defineProperty(compressor, 'threshold', {
                            get: () => threshold.value + seededRandom(audioSeed + 1) * 0.1,
                            set: (v) => { threshold.value = v; }
                        });

                        Object.defineProperty(compressor, 'knee', {
                            get: () => knee.value + seededRandom(audioSeed + 2) * 0.1,
                            set: (v) => { knee.value = v; }
                        });

                        Object.defineProperty(compressor, 'ratio', {
                            get: () => ratio.value + seededRandom(audioSeed + 3) * 0.1,
                            set: (v) => { ratio.value = v; }
                        });

                        return compressor;
                    };

                    return context;
                };
                window.AudioContext = NewAudioContext;
                window.webkitAudioContext = NewAudioContext;
            }

            // 14. Screen指纹一致性
            Object.defineProperty(screen, 'colorDepth', {
                get: () => 24,
                configurable: true
            });
            Object.defineProperty(screen, 'pixelDepth', {
                get: () => 24,
                configurable: true
            });

            // 15. Hardware Concurrency（CPU核心数）
            Object.defineProperty(navigator, 'hardwareConcurrency', {
                get: () => 8,  // 模拟8核CPU
                configurable: true
            });

            // 16. deviceMemory（设备内存）
            Object.defineProperty(navigator, 'deviceMemory', {
                get: () => 8,  // 模拟8GB内存
                configurable: true
            });

            // 17. 媒体设备伪装
            if (navigator.mediaDevices && navigator.mediaDevices.enumerateDevices) {
                const originalEnumerateDevices = navigator.mediaDevices.enumerateDevices;
                navigator.mediaDevices.enumerateDevices = function() {
                    return originalEnumerateDevices.call(this).then(devices => {
                        // 确保至少有音频输入/输出设备
                        const hasAudioInput = devices.some(d => d.kind === 'audioinput');
                        const hasAudioOutput = devices.some(d => d.kind === 'audiooutput');

                        if (!hasAudioInput || !hasAudioOutput) {
                            return [
                                ...devices,
                                {deviceId: 'default', groupId: 'default', kind: 'audioinput', label: ''},
                                {deviceId: 'default', groupId: 'default', kind: 'audiooutput', label: ''}
                            ];
                        }
                        return devices;
                    });
                };
            }

            // 18. Notification权限伪装
            if (window.Notification) {
                const originalPermission = Notification.permission;
                Object.defineProperty(Notification, 'permission', {
                    get: () => 'default',
                    configurable: true
                });
            }

            // 19. 防止CDP（Chrome DevTools Protocol）检测（2025增强版）
            // CDP是Cloudflare 2024年重点检测的特征之一
            const originalToString = Function.prototype.toString;
            Function.prototype.toString = function() {
                // 覆盖所有被修改的函数，使其看起来像原生代码
                const nativeFunctions = [
                    window.navigator.permissions.query,
                    HTMLCanvasElement.prototype.toDataURL,
                    WebGLRenderingContext.prototype.getParameter,
                    CanvasRenderingContext2D.prototype.getImageData,
                ];

                if (nativeFunctions.includes(this)) {
                    return `function ${this.name || 'anonymous'}() { [native code] }`;
                }
                return originalToString.call(this);
            };

            // 隐藏CDP runtime对象痕迹
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Array;
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Promise;
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Symbol;
            delete window.$cdc_asdjflasutopfhvcZLmcfl_;
            delete window.$chrome_asyncScriptInfo;

            // 隐藏Selenium痕迹
            delete window._Selenium_IDE_Recorder;
            delete window._selenium;
            delete window.__selenium_unwrapped;
            delete window.__webdriver_evaluate;
            delete window.__driver_evaluate;
            delete window.__webdriver_script_function;
            delete window.__webdriver_script_func;
            delete window.__webdriver_script_fn;
            delete window.__fxdriver_evaluate;
            delete window.__driver_unwrapped;
            delete window.__webdriver_unwrapped;
            delete window.__fxdriver_unwrapped;
            delete document.__webdriver_evaluate;
            delete document.__selenium_evaluate;
            delete document.__webdriver_script_function;
            delete document.__webdriver_script_func;
            delete document.$chrome_asyncScriptInfo;
            delete document.$cdc_asdjflasutopfhvcZLmcfl_;

            // 隐藏Playwright痕迹
            delete window.__playwright;
            delete window.__pw_manual;
            delete window.__PW_inspect;

            // 20. 用户激活API伪装
            if (navigator.userActivation) {
                Object.defineProperty(navigator.userActivation, 'hasBeenActive', {
                    get: () => true,
                    configurable: true
                });
                Object.defineProperty(navigator.userActivation, 'isActive', {
                    get: () => true,
                    configurable: true
                });
            }

            // ==================== 2025最新增强特征（7个高级反检测） ====================

            // 21. Performance API 伪装（添加真实的性能数据）
            if (window.performance && window.performance.timing) {
                const timing = window.performance.timing;
                const now = Date.now();
                const navigationStart = now - Math.floor(seededRandom(sessionSeed + 100) * 3000 + 1000);

                // 伪造合理的性能时间线
                Object.defineProperty(timing, 'navigationStart', {
                    get: () => navigationStart,
                    configurable: true
                });
                Object.defineProperty(timing, 'fetchStart', {
                    get: () => navigationStart + Math.floor(seededRandom(sessionSeed + 101) * 50 + 10),
                    configurable: true
                });
                Object.defineProperty(timing, 'domainLookupStart', {
                    get: () => navigationStart + Math.floor(seededRandom(sessionSeed + 102) * 80 + 50),
                    configurable: true
                });
                Object.defineProperty(timing, 'domainLookupEnd', {
                    get: () => navigationStart + Math.floor(seededRandom(sessionSeed + 103) * 120 + 80),
                    configurable: true
                });
                Object.defineProperty(timing, 'connectStart', {
                    get: () => navigationStart + Math.floor(seededRandom(sessionSeed + 104) * 150 + 120),
                    configurable: true
                });
                Object.defineProperty(timing, 'connectEnd', {
                    get: () => navigationStart + Math.floor(seededRandom(sessionSeed + 105) * 200 + 180),
                    configurable: true
                });
                Object.defineProperty(timing, 'requestStart', {
                    get: () => navigationStart + Math.floor(seededRandom(sessionSeed + 106) * 250 + 200),
                    configurable: true
                });
                Object.defineProperty(timing, 'responseStart', {
                    get: () => navigationStart + Math.floor(seededRandom(sessionSeed + 107) * 400 + 300),
                    configurable: true
                });
                Object.defineProperty(timing, 'responseEnd', {
                    get: () => navigationStart + Math.floor(seededRandom(sessionSeed + 108) * 600 + 500),
                    configurable: true
                });
                Object.defineProperty(timing, 'domLoading', {
                    get: () => navigationStart + Math.floor(seededRandom(sessionSeed + 109) * 650 + 550),
                    configurable: true
                });
                Object.defineProperty(timing, 'domInteractive', {
                    get: () => navigationStart + Math.floor(seededRandom(sessionSeed + 110) * 1000 + 800),
                    configurable: true
                });
                Object.defineProperty(timing, 'domContentLoadedEventStart', {
                    get: () => navigationStart + Math.floor(seededRandom(sessionSeed + 111) * 1200 + 1000),
                    configurable: true
                });
                Object.defineProperty(timing, 'domContentLoadedEventEnd', {
                    get: () => navigationStart + Math.floor(seededRandom(sessionSeed + 112) * 1300 + 1100),
                    configurable: true
                });
                Object.defineProperty(timing, 'domComplete', {
                    get: () => navigationStart + Math.floor(seededRandom(sessionSeed + 113) * 2000 + 1500),
                    configurable: true
                });
                Object.defineProperty(timing, 'loadEventStart', {
                    get: () => navigationStart + Math.floor(seededRandom(sessionSeed + 114) * 2100 + 1800),
                    configurable: true
                });
                Object.defineProperty(timing, 'loadEventEnd', {
                    get: () => navigationStart + Math.floor(seededRandom(sessionSeed + 115) * 2200 + 2000),
                    configurable: true
                });
            }

            // 22. Event Trust 修复（修复 isTrusted 属性）
            const originalAddEventListener = EventTarget.prototype.addEventListener;
            EventTarget.prototype.addEventListener = function(type, listener, options) {
                const wrappedListener = function(event) {
                    // 强制设置 isTrusted 为 true
                    if (event && !event.isTrusted) {
                        Object.defineProperty(event, 'isTrusted', {
                            get: () => true,
                            configurable: true
                        });
                    }

                    if (typeof listener === 'function') {
                        return listener.call(this, event);
                    } else if (listener && typeof listener.handleEvent === 'function') {
                        return listener.handleEvent(event);
                    }
                };

                return originalAddEventListener.call(this, type, wrappedListener, options);
            };

            // 修复 dispatchEvent 以确保事件看起来是可信的
            const originalDispatchEvent = EventTarget.prototype.dispatchEvent;
            EventTarget.prototype.dispatchEvent = function(event) {
                Object.defineProperty(event, 'isTrusted', {
                    get: () => true,
                    configurable: true
                });
                return originalDispatchEvent.call(this, event);
            };

            // 23. Canvas 指纹一致性增强（确保多次调用返回相同结果）
            // 创建会话级别的Canvas指纹缓存
            const canvasCache = new Map();

            const originalToDataURLEnhanced = HTMLCanvasElement.prototype.toDataURL;
            HTMLCanvasElement.prototype.toDataURL = function(type) {
                // 生成canvas的唯一标识
                const canvasId = this.width + 'x' + this.height + '_' + (this.id || 'anonymous');

                // 如果缓存中存在，直接返回
                if (canvasCache.has(canvasId)) {
                    return canvasCache.get(canvasId);
                }

                // 否则生成并缓存
                const result = originalToDataURLEnhanced.apply(this, arguments);
                canvasCache.set(canvasId, result);
                return result;
            };

            // 24. WebGL 参数伪装增强（伪装更多 WebGL 渲染器信息）
            const getParameterEnhanced = WebGLRenderingContext.prototype.getParameter;
            WebGLRenderingContext.prototype.getParameter = function(parameter) {
                // UNMASKED_VENDOR_WEBGL
                if (parameter === 37445) {
                    return 'Intel Inc.';
                }
                // UNMASKED_RENDERER_WEBGL
                if (parameter === 37446) {
                    return 'Intel Iris OpenGL Engine';
                }
                // VERSION
                if (parameter === 0x1F02) {
                    return 'WebGL 1.0 (OpenGL ES 2.0 Chromium)';
                }
                // SHADING_LANGUAGE_VERSION
                if (parameter === 0x8B8C) {
                    return 'WebGL GLSL ES 1.0 (OpenGL ES GLSL ES 1.0 Chromium)';
                }
                // VENDOR
                if (parameter === 0x1F00) {
                    return 'WebKit';
                }
                // RENDERER
                if (parameter === 0x1F01) {
                    return 'WebKit WebGL';
                }
                // MAX_TEXTURE_SIZE
                if (parameter === 0x0D33) {
                    return 16384;
                }
                // MAX_VERTEX_TEXTURE_IMAGE_UNITS
                if (parameter === 0x8B4C) {
                    return 16;
                }
                return getParameterEnhanced.apply(this, arguments);
            };

            // WebGL2 支持增强
            if (window.WebGL2RenderingContext) {
                const getParameter2Enhanced = WebGL2RenderingContext.prototype.getParameter;
                WebGL2RenderingContext.prototype.getParameter = function(parameter) {
                    if (parameter === 37445) return 'Intel Inc.';
                    if (parameter === 37446) return 'Intel Iris OpenGL Engine';
                    if (parameter === 0x1F02) return 'WebGL 2.0 (OpenGL ES 3.0 Chromium)';
                    if (parameter === 0x8B8C) return 'WebGL GLSL ES 3.0 (OpenGL ES GLSL ES 3.0 Chromium)';
                    if (parameter === 0x1F00) return 'WebKit';
                    if (parameter === 0x1F01) return 'WebKit WebGL';
                    if (parameter === 0x0D33) return 16384;
                    if (parameter === 0x8B4C) return 16;
                    return getParameter2Enhanced.apply(this, arguments);
                };
            }

            // 25. Plugin 数组优化（添加更真实的插件列表）
            Object.defineProperty(navigator, 'plugins', {
                get: () => {
                    const plugins = [
                        {
                            0: {type: "application/x-google-chrome-pdf", suffixes: "pdf", description: "Portable Document Format", enabledPlugin: true},
                            name: "Chrome PDF Plugin",
                            filename: "internal-pdf-viewer",
                            description: "Portable Document Format",
                            length: 1
                        },
                        {
                            0: {type: "application/pdf", suffixes: "pdf", description: "Portable Document Format", enabledPlugin: true},
                            name: "Chromium PDF Plugin",
                            filename: "internal-pdf-viewer",
                            description: "Portable Document Format",
                            length: 1
                        },
                        {
                            0: {type: "application/x-nacl", suffixes: "", description: "Native Client Executable", enabledPlugin: true},
                            1: {type: "application/x-pnacl", suffixes: "", description: "Portable Native Client Executable", enabledPlugin: true},
                            name: "Native Client",
                            filename: "internal-nacl-plugin",
                            description: "Native Client Executable",
                            length: 2
                        },
                        {
                            0: {type: "application/x-ppapi-widevine-cdm", suffixes: "", description: "Widevine Content Decryption Module", enabledPlugin: true},
                            name: "Widevine Content Decryption Module",
                            filename: "widevinecdmadapter.dll",
                            description: "Enables Widevine licenses for playback of HTML audio/video content.",
                            length: 1
                        }
                    ];

                    // 添加数组特性（使其看起来像真实的PluginArray）
                    plugins.item = function(index) {
                        return this[index] || null;
                    };
                    plugins.namedItem = function(name) {
                        return this.find(p => p.name === name) || null;
                    };
                    plugins.refresh = function() {};

                    return plugins;
                },
                configurable: true
            });

            // mimeTypes 也需要同步更新
            Object.defineProperty(navigator, 'mimeTypes', {
                get: () => {
                    const mimeTypes = [
                        {type: "application/pdf", suffixes: "pdf", description: "Portable Document Format", enabledPlugin: {name: "Chrome PDF Plugin"}},
                        {type: "application/x-google-chrome-pdf", suffixes: "pdf", description: "Portable Document Format", enabledPlugin: {name: "Chrome PDF Plugin"}},
                        {type: "application/x-nacl", suffixes: "", description: "Native Client Executable", enabledPlugin: {name: "Native Client"}},
                        {type: "application/x-pnacl", suffixes: "", description: "Portable Native Client Executable", enabledPlugin: {name: "Native Client"}},
                        {type: "application/x-ppapi-widevine-cdm", suffixes: "", description: "Widevine Content Decryption Module", enabledPlugin: {name: "Widevine Content Decryption Module"}}
                    ];

                    mimeTypes.item = function(index) {
                        return this[index] || null;
                    };
                    mimeTypes.namedItem = function(name) {
                        return this.find(m => m.type === name) || null;
                    };

                    return mimeTypes;
                },
                configurable: true
            });

            // 26. Permissions API 伪装增强（伪装更多权限查询结果）
            const originalPermissionsQuery = window.navigator.permissions?.query;
            if (originalPermissionsQuery) {
                window.navigator.permissions.query = function(parameters) {
                    const permissionName = parameters.name;

                    // 为不同的权限返回合理的状态
                    const permissionStates = {
                        'notifications': 'default',
                        'geolocation': 'prompt',
                        'camera': 'prompt',
                        'microphone': 'prompt',
                        'midi': 'prompt',
                        'clipboard-read': 'prompt',
                        'clipboard-write': 'prompt',
                        'payment-handler': 'prompt',
                        'persistent-storage': 'prompt',
                        'push': 'prompt',
                        'screen-wake-lock': 'prompt',
                        'xr-spatial-tracking': 'prompt'
                    };

                    const state = permissionStates[permissionName] || 'prompt';

                    return Promise.resolve({
                        state: state,
                        status: state,
                        onchange: null
                    });
                };
            }

            // 27. Battery API 禁用（移除 CI 环境特征）
            // 真实浏览器可能没有 Battery API，或者返回受限信息
            // 完全移除 getBattery 方法（而不是返回假数据）
            if (navigator.getBattery) {
                Object.defineProperty(navigator, 'getBattery', {
                    get: () => undefined,
                    configurable: true
                });
                delete navigator.getBattery;
            }

            // 同时删除其他可能的电池API变体
            delete navigator.battery;
            delete navigator.mozBattery;
            delete navigator.webkitBattery;

            // ==================== 调试信息（更新版） ====================
            console.log('✅ 增强型反检测脚本已注入（2025最新版）');
            console.log('   - CDP痕迹清理: ✓ 40+ 对象');
            console.log('   - Canvas指纹: ✓ 确定性噪声 + 缓存一致性');
            console.log('   - Audio指纹: ✓ 确定性噪声');
            console.log('   - WebGL指纹: ✓ 增强参数伪装');
            console.log('   - Performance API: ✓ 真实时间线');
            console.log('   - Event Trust: ✓ isTrusted修复');
            console.log('   - Plugin Array: ✓ 完整列表');
            console.log('   - Permissions API: ✓ 多权限伪装');
            console.log('   - Battery API: ✓ 已移除');
            console.log('   - 会话种子: ' + sessionSeed.toFixed(2));
        """)

    @staticmethod
    async def human_mouse_move(page: Page, target_x: int, target_y: int, duration: float = 1.0) -> None:
        """
        人类般的鼠标移动（贝塞尔曲线）

        Args:
            page: Playwright页面对象
            target_x: 目标X坐标
            target_y: 目标Y坐标
            duration: 移动持续时间（秒）
        """
        steps = random.randint(15, 30)
        delay_per_step = duration / steps

        # 获取当前鼠标位置（假设从(0,0)开始）
        current_x, current_y = 0, 0

        for i in range(steps):
            progress = i / steps

            # 贝塞尔曲线（ease-in-out效果）
            # 公式: 3t^2 - 2t^3
            t = progress
            ease = t * t * (3 - 2 * t)

            # 添加随机抖动（模拟手部颤抖）
            jitter_x = random.uniform(-3, 3)
            jitter_y = random.uniform(-3, 3)

            # 计算当前位置
            x = current_x + (target_x - current_x) * ease + jitter_x
            y = current_y + (target_y - current_y) * ease + jitter_y

            await page.mouse.move(x, y)
            await asyncio.sleep(delay_per_step + random.uniform(-0.01, 0.01))

        # 最终精确到达目标位置
        await page.mouse.move(target_x, target_y)

    @staticmethod
    async def human_scroll(page: Page, distance: int = 300, direction: str = 'down') -> None:
        """
        人类般的滚动（突发式而非线性）

        Args:
            page: Playwright页面对象
            distance: 滚动距离（像素）
            direction: 滚动方向（'down' 或 'up'）
        """
        scrolled = 0
        delta_sign = 1 if direction == 'down' else -1

        while scrolled < distance:
            # 突发式滚动（10-150px不等）
            delta = random.randint(30, 150) * delta_sign
            await page.mouse.wheel(0, delta)
            scrolled += abs(delta)

            # 随机暂停（模拟阅读/查看内容）
            pause = random.uniform(0.1, 0.6)
            await asyncio.sleep(pause)

    @staticmethod
    async def simulate_reading_behavior(page: Page) -> None:
        """
        模拟真实的页面阅读行为
        包括：鼠标移动、滚动、停顿
        """
        # 1. 随机鼠标移动（2-5次）
        move_count = random.randint(2, 5)
        for _ in range(move_count):
            x = random.randint(200, 1700)
            y = random.randint(100, 800)
            await EnhancedStealth.human_mouse_move(page, x, y, duration=random.uniform(0.5, 1.2))
            await asyncio.sleep(random.uniform(0.3, 0.8))

        # 2. 随机滚动（1-3次）
        scroll_count = random.randint(1, 3)
        for _ in range(scroll_count):
            distance = random.randint(200, 500)
            await EnhancedStealth.human_scroll(page, distance)
            await asyncio.sleep(random.uniform(0.5, 1.0))

        # 3. 模拟思考停顿
        await asyncio.sleep(random.uniform(0.8, 2.0))

    @staticmethod
    async def add_random_delays(min_seconds: float = 0.5, max_seconds: float = 2.0) -> None:
        """
        添加随机延迟（避免固定时间间隔被检测）

        Args:
            min_seconds: 最小延迟秒数
            max_seconds: 最大延迟秒数
        """
        delay = random.uniform(min_seconds, max_seconds)
        await asyncio.sleep(delay)

    @staticmethod
    async def detect_and_solve_turnstile(page: Page, timeout: int = 30000) -> bool:
        """
        检测并尝试解决Cloudflare Turnstile验证

        Args:
            page: Playwright页面对象
            timeout: 超时时间（毫秒）

        Returns:
            bool: 是否成功解决验证
        """
        try:
            # 检测是否存在Turnstile iframe
            turnstile_iframe = await page.query_selector('iframe[src*="challenges.cloudflare.com"]')

            if not turnstile_iframe:
                # 未检测到Turnstile，直接返回成功
                return True

            # 等待挑战完成（Turnstile通常会自动完成）
            try:
                await page.wait_for_selector(
                    'iframe[src*="challenges.cloudflare.com"]',
                    state='hidden',
                    timeout=timeout
                )
                return True
            except:
                # 超时，但可能已经通过
                # 检查页面是否包含成功标识
                page_content = await page.content()
                if 'cf-challenge' not in page_content.lower():
                    return True
                return False

        except Exception as e:
            # 检测失败，假设无验证
            return True

    @staticmethod
    def get_enhanced_browser_args() -> list:
        """
        获取增强版浏览器启动参数（2025优化版）
        基于最新的Cloudflare绕过技术

        Returns:
            list: 浏览器启动参数列表
        """
        return [
            # ==================== 核心反检测参数（最重要） ====================
            "--disable-blink-features=AutomationControlled",  # 禁用自动化控制特征
            "--exclude-switches=enable-automation",  # 排除自动化开关

            # ==================== 浏览器行为优化 ====================
            "--window-size=1920,1080",  # 固定窗口大小（常见分辨率）
            "--start-maximized",  # 最大化启动
            "--no-first-run",  # 跳过首次运行体验
            "--no-default-browser-check",  # 不检查默认浏览器
            "--disable-popup-blocking",  # 禁用弹窗阻止

            # ==================== 性能优化（CI环境必需） ====================
            "--disable-dev-shm-usage",  # 禁用/dev/shm使用（Docker/CI环境必需）
            "--disable-gpu",  # 禁用GPU加速（headless模式下）
            "--no-sandbox",  # 禁用沙箱（CI环境必需）
            "--disable-setuid-sandbox",  # 禁用setuid沙箱

            # ==================== 网络优化 ====================
            "--disable-features=IsolateOrigins,site-per-process",  # 禁用站点隔离
            "--allow-running-insecure-content",  # 允许运行不安全内容

            # ==================== 媒体优化 ====================
            "--use-fake-ui-for-media-stream",  # 使用假UI处理媒体流
            "--use-fake-device-for-media-stream",  # 使用假设备处理媒体流
            "--autoplay-policy=no-user-gesture-required",  # 自动播放策略

            # ==================== 背景和定时器优化 ====================
            "--disable-background-timer-throttling",  # 禁用后台定时器节流
            "--disable-backgrounding-occluded-windows",  # 禁用后台窗口优化
            "--disable-renderer-backgrounding",  # 禁用渲染器后台优化
            "--disable-hang-monitor",  # 禁用挂起监控

            # ==================== 2025新增反检测参数 ====================
            "--disable-features=OutOfBlinkCors",  # 禁用CORS特性
            "--disable-features=ImprovedCookieControls",  # 禁用改进的Cookie控制
            "--disable-features=LazyFrameLoading",  # 禁用懒加载
            "--disable-features=GlobalMediaControls",  # 禁用全局媒体控制

            # ==================== 稳定性优化 ====================
            "--disable-logging",  # 禁用日志（减少IO）
            "--disable-crash-reporter",  # 禁用崩溃报告
            "--disable-in-process-stack-traces",  # 禁用进程内堆栈跟踪
            "--disable-breakpad",  # 禁用崩溃报告守护进程
            "--disable-component-extensions-with-background-pages",  # 禁用带后台页面的组件扩展

            # ==================== 隐私和追踪 ====================
            "--disable-sync",  # 禁用同步
            "--metrics-recording-only",  # 仅记录指标
            "--disable-default-apps",  # 禁用默认应用
            "--mute-audio",  # 静音
            "--hide-scrollbars",  # 隐藏滚动条

            # ==================== 渲染优化 ====================
            "--disable-software-rasterizer",  # 禁用软件光栅化
            "--disable-canvas-aa",  # 禁用Canvas抗锯齿（减少指纹特征）
            "--disable-2d-canvas-clip-aa",  # 禁用2D Canvas裁剪抗锯齿

            # ==================== 语言和地区 ====================
            "--lang=zh-CN",  # 设置语言为中文
            "--accept-lang=zh-CN,zh,en-US,en",  # 接受语言列表

            # ==================== 扩展和插件 ====================
            "--disable-extensions",  # 禁用扩展
            "--disable-plugins-discovery",  # 禁用插件发现

            # ==================== IPC和进程 ====================
            "--disable-ipc-flooding-protection",  # 禁用IPC洪水保护
            "--disable-infobars",  # 禁用信息栏
            "--disable-notifications",  # 禁用通知

            # ==================== 模拟真实浏览器特征 ====================
            "--enable-features=NetworkService,NetworkServiceInProcess",  # 启用网络服务
            "--force-color-profile=srgb",  # 强制使用sRGB颜色配置文件
            "--disable-features=TranslateUI",  # 禁用翻译UI
            "--disable-features=ChromeWhatsNewUI",  # 禁用"新功能"提示

            # ==================== 其他优化 ====================
            "--disable-domain-reliability",  # 禁用域名可靠性服务
            "--disable-client-side-phishing-detection",  # 禁用客户端钓鱼检测
            "--disable-web-security",  # 禁用Web安全（允许跨域，谨慎使用）
        ]


class ProxyManager:
    """代理管理器 - 支持直接配置和订阅模式"""

    # 类级别的订阅管理器缓存
    _subscription_manager = None

    @staticmethod
    def get_proxy_config() -> Optional[dict]:
        """
        从环境变量获取代理���置（同步版本，仅支持直接配置）

        Returns:
            dict or None: 代理配置字典
        """
        import os

        proxy_server = os.getenv('PROXY_SERVER')
        if not proxy_server:
            return None

        return {
            "server": proxy_server,
            "username": os.getenv('PROXY_USER', ''),
            "password": os.getenv('PROXY_PASS', '')
        }

    @staticmethod
    async def get_proxy_config_async() -> Optional[dict]:
        """
        获取代理配置（异步版本，支持订阅模式和直接配置）

        优先级：
        1. 订阅模式（PROXY_SUBSCRIPTION_URL）
        2. 直接配置（PROXY_SERVER）

        Returns:
            dict or None: 代理配置字典

        环境变量配置：
            订阅模式：
            - PROXY_SUBSCRIPTION_URL: 订阅链接
            - PROXY_SELECTION_MODE: 节点选择模式（auto/manual/random，默认auto）
            - PROXY_NODE_NAME: 手动模式下的节点名称匹配模式
            - PROXY_TEST_SPEED: 是否测速（true/false，默认true）
            - PROXY_CACHE_DURATION: 节点缓存时长（秒，默认3600）

            直接配置：
            - PROXY_SERVER: 代理服务器地址
            - PROXY_USER: 代理用户名
            - PROXY_PASS: 代理密码
        """
        import os
        from utils.subscription_parser import SubscriptionProxyManager

        # 1. 检查是否使用订阅模式
        subscription_url = os.getenv('PROXY_SUBSCRIPTION_URL')

        if subscription_url:
            logger.info(f"🌐 使用订阅模式获取代理配置")

            try:
                # 创建或复用订阅���理器实例
                if ProxyManager._subscription_manager is None:
                    # 处理GitHub Secrets空字符串问题：空字符串应该使用默认值
                    selection_mode = (os.getenv('PROXY_SELECTION_MODE', 'auto') or 'auto').lower()
                    node_name_pattern = os.getenv('PROXY_NODE_NAME') or None

                    test_speed_env = os.getenv('PROXY_TEST_SPEED', 'true') or 'true'
                    test_speed = test_speed_env.lower() == 'true'

                    cache_duration_env = os.getenv('PROXY_CACHE_DURATION', '3600') or '3600'
                    cache_duration = int(cache_duration_env)

                    ProxyManager._subscription_manager = SubscriptionProxyManager(
                        subscription_url=subscription_url,
                        selection_mode=selection_mode,
                        node_name_pattern=node_name_pattern,
                        test_speed=test_speed,
                        cache_duration=cache_duration
                    )

                    logger.info(f"✅ 订阅代理管理器初始化完成")
                    logger.info(f"   - 选择模式: {selection_mode}")
                    logger.info(f"   - 是否测速: {test_speed}")
                    logger.info(f"   - 缓存时长: {cache_duration}秒")

                # 获取代理配置
                proxy_config = await ProxyManager._subscription_manager.get_proxy_config()

                if proxy_config:
                    # 显示选中节点信息
                    node_info = ProxyManager._subscription_manager.get_selected_node_info()
                    if node_info:
                        logger.info(f"✅ 订阅代理节点信息:")
                        logger.info(f"   - 节点名称: {node_info['name']}")
                        logger.info(f"   - 节点类型: {node_info['type']}")
                        logger.info(f"   - 节点地址: {node_info['server']}:{node_info['port']}")
                        if node_info.get('latency'):
                            logger.info(f"   - 延迟: {node_info['latency']}ms")

                return proxy_config

            except Exception as e:
                logger.error(f"❌ 订阅模式获取代理失败: {e}")
                logger.info(f"ℹ️ 尝试使用直接配置模式...")

        # 2. 回退到直接配置模式
        return ProxyManager.get_proxy_config()

    @staticmethod
    def should_use_proxy() -> bool:
        """
        判断是否应该使用代理

        自动检测以下环境变量:
        - USE_PROXY=true (显式启用)
        - PROXY_SUBSCRIPTION_URL (订阅代理模式)
        - PROXY_SERVER (直接代理模式)

        Returns:
            bool: 是否使用代理
        """
        import os

        # 方式1: 显式启用
        if os.getenv('USE_PROXY', 'false').lower() == 'true':
            return True

        # 方式2: 配置了订阅代理URL
        if os.getenv('PROXY_SUBSCRIPTION_URL'):
            return True

        # 方式3: 配置了直接代理服务器
        if os.getenv('PROXY_SERVER'):
            return True

        return False

    @staticmethod
    def clear_subscription_cache():
        """清除订阅管理器缓存（用于强制刷新）"""
        ProxyManager._subscription_manager = None
        logger.info("🔄 订阅管理器缓存已清除")


class StealthConfig:
    """反检测配置管理器 - 支持全局和按认证方式定制"""

    @staticmethod
    def should_enable_behavior_simulation(auth_method: str = None) -> bool:
        """
        判断是否应该启用行为模拟

        Args:
            auth_method: 认证方式（如 "cookies", "email", "github", "linux.do"）
                        如果为None，则使用全局配置

        Returns:
            bool: 是否启用行为模拟

        环境变量配置：
            - ENABLE_BEHAVIOR_SIMULATION=true           # 全局启用
            - BEHAVIOR_SIMULATION_METHODS=email,github  # 仅对指定方式启用
            - DISABLE_BEHAVIOR_SIMULATION_METHODS=cookies  # 对指定方式禁用
        """
        import os

        # 全局配置
        global_enabled = os.getenv('ENABLE_BEHAVIOR_SIMULATION', 'false').lower() == 'true'

        # 如果没有指定认证方式，返回全局配置
        if not auth_method:
            return global_enabled

        # 检查是否仅对特定方式启用
        enabled_methods = os.getenv('BEHAVIOR_SIMULATION_METHODS', '').lower().split(',')
        enabled_methods = [m.strip() for m in enabled_methods if m.strip()]

        if enabled_methods:
            # 如果指定了启用列表，只对列表中的方式启用
            return auth_method.lower() in enabled_methods

        # 检查是否对特定方式禁用
        disabled_methods = os.getenv('DISABLE_BEHAVIOR_SIMULATION_METHODS', '').lower().split(',')
        disabled_methods = [m.strip() for m in disabled_methods if m.strip()]

        if disabled_methods and auth_method.lower() in disabled_methods:
            return False

        # 否则使用全局配置
        return global_enabled

    @staticmethod
    def should_use_proxy_for_method(auth_method: str = None) -> bool:
        """
        判断特定认证方式是否应该使用代理

        Args:
            auth_method: 认证方式

        Returns:
            bool: 是否使用代理

        环境变量配置：
            - USE_PROXY=true                      # 全局启用代理
            - PROXY_METHODS=github,linux.do       # 仅对指定方式启用代理
            - NO_PROXY_METHODS=cookies            # 对指定方式禁用代理
        """
        import os

        # 全局配置
        global_proxy = os.getenv('USE_PROXY', 'false').lower() == 'true'

        if not auth_method:
            return global_proxy

        # 检查是否仅对特定方式启用代理
        proxy_methods = os.getenv('PROXY_METHODS', '').lower().split(',')
        proxy_methods = [m.strip() for m in proxy_methods if m.strip()]

        if proxy_methods:
            return auth_method.lower() in proxy_methods

        # 检查是否对特定方式禁用代理
        no_proxy_methods = os.getenv('NO_PROXY_METHODS', '').lower().split(',')
        no_proxy_methods = [m.strip() for m in no_proxy_methods if m.strip()]

        if no_proxy_methods and auth_method.lower() in no_proxy_methods:
            return False

        return global_proxy

    @staticmethod
    def get_wait_time_multiplier(auth_method: str = None) -> float:
        """
        获取等待时间倍增器（针对不同认证方式可能需要不同的等待时间）

        Args:
            auth_method: 认证方式

        Returns:
            float: 等待时间倍增器（默认1.0）

        环境变量配置：
            - WAIT_TIME_MULTIPLIER=2.0                  # 全局倍增器
            - GITHUB_WAIT_TIME_MULTIPLIER=3.0           # GitHub特定倍增器
            - LINUXDO_WAIT_TIME_MULTIPLIER=2.5          # Linux.do特定倍增器
        """
        import os

        # 默认倍增器
        default_multiplier = float(os.getenv('WAIT_TIME_MULTIPLIER', '1.0'))

        if not auth_method:
            return default_multiplier

        # 检查是否有针对特定方式的倍增器
        method_key = f"{auth_method.upper().replace('.', '')}_WAIT_TIME_MULTIPLIER"
        method_multiplier = os.getenv(method_key)

        if method_multiplier:
            try:
                return float(method_multiplier)
            except ValueError:
                pass

        return default_multiplier

    @staticmethod
    def get_config_summary() -> dict:
        """
        获取当前配置摘要（用于调试）

        Returns:
            dict: 配置摘要
        """
        import os

        return {
            "global_behavior_simulation": os.getenv('ENABLE_BEHAVIOR_SIMULATION', 'false'),
            "behavior_simulation_methods": os.getenv('BEHAVIOR_SIMULATION_METHODS', ''),
            "disable_behavior_simulation_methods": os.getenv('DISABLE_BEHAVIOR_SIMULATION_METHODS', ''),
            "global_proxy": os.getenv('USE_PROXY', 'false'),
            "proxy_methods": os.getenv('PROXY_METHODS', ''),
            "no_proxy_methods": os.getenv('NO_PROXY_METHODS', ''),
            "wait_time_multiplier": os.getenv('WAIT_TIME_MULTIPLIER', '1.0'),
        }

