# Архитектура проекта MSFS AutoLand - Диаграммы

**Дата:** 2026-04-16  
**Версия:** 1.0

---

## Как визуализировать эти диаграммы:

### Вариант 1: Online (быстро)
1. Откройте https://mermaid.live/
2. Скопируйте код диаграммы
3. Вставьте в редактор
4. Диаграмма отобразится автоматически
5. Можно экспортировать в PNG/SVG

### Вариант 2: VS Code (удобно)
1. Установите расширение "Markdown Preview Mermaid Support"
2. Откройте этот файл в VS Code
3. Нажмите Ctrl+Shift+V (Preview)
4. Диаграммы отобразятся в превью

### Вариант 3: Standalone приложение
1. Скачайте Mermaid CLI: `npm install -g @mermaid-js/mermaid-cli`
2. Запустите: `mmdc -i ARCHITECTURE.md -o architecture.png`

### Вариант 4: GitHub/GitLab
- Просто откройте этот файл на GitHub/GitLab
- Диаграммы отобразятся автоматически

---

## Диаграмма 1: Архитектура системы

Показывает общую структуру проекта и взаимодействие основных компонентов.

\`\`\`mermaid
graph TB
    subgraph "Microsoft Flight Simulator"
        MSFS[MSFS 2020/2024]
        SimConnect[SimConnect API]
        WASM[MobiFlight WASM]
    end

    subgraph "MSFS AutoLand System"
        subgraph "Главное приложение"
            Main[main.py<br/>AutoLandSystem]
            GUI[gui.py<br/>AutoLandGUI]
        end

        subgraph "Ввод данных"
            Telemetry[telemetry.py<br/>MSFSTelemetry]
            AirportReader[msfs_airport_reader.py<br/>MSFSAirportReader]
            FMSReader[fms_reader.py<br/>FMSReader]
        end

        subgraph "Адаптеры самолётов"
            AircraftAdapter[aircraft_adapter.py<br/>AircraftCommandAdapter]
            WASMInterface[wasm_interface.py<br/>MobiFlightWASM]
            Profiles[aircraft_profiles.json<br/>Профили самолётов]
        end

        subgraph "Навигация"
            Navigation[navigation.py<br/>Navigation]
            ILSNav[ils_navigation.py<br/>ILSNavigation]
            DMENav[dme_navigation.py<br/>DMENavigation]
            WindCorr[wind_correction.py<br/>WindCorrection]
        end

        subgraph "Управление"
            Control[control.py<br/>MSFSControl]
            Autothrottle[autothrottle.py<br/>AutothrottleController]
            FlareCtrl[flare_controller.py<br/>FlareController]
            VJoy[virtual_joystick.py<br/>VirtualJoystick]
        end

        subgraph "Мониторинг"
            StabMonitor[stabilized_approach.py<br/>StabilizedApproachMonitor]
        end

        subgraph "База данных"
            AirportsDB[airports_database.py<br/>AirportsDatabase]
            AirportsJSON[airports_database.json<br/>8 аэропортов]
        end

        subgraph "Диалоги"
            ApproachDialog[approach_dialog.py<br/>ApproachConfigDialog]
        end
    end

    subgraph "Внешние устройства"
        vJoyDriver[vJoy Driver]
    end

    %% Связи MSFS -> Ввод данных
    MSFS --> SimConnect
    MSFS --> WASM
    SimConnect --> Telemetry
    SimConnect --> AirportReader
    SimConnect --> FMSReader
    WASM --> WASMInterface

    %% Связи Ввод данных -> Главное приложение
    Telemetry --> Main
    AirportReader --> Main
    FMSReader --> Main

    %% Связи Адаптеры
    Telemetry --> AircraftAdapter
    WASMInterface --> AircraftAdapter
    Profiles --> AircraftAdapter
    AircraftAdapter --> Main

    %% Связи Навигация
    Telemetry --> Navigation
    Telemetry --> ILSNav
    Telemetry --> DMENav
    Telemetry --> WindCorr
    Navigation --> Main
    ILSNav --> Main
    DMENav --> Main
    WindCorr --> Main

    %% Связи Управление
    Main --> Control
    Main --> Autothrottle
    Main --> FlareCtrl
    Control --> SimConnect
    Autothrottle --> VJoy
    FlareCtrl --> VJoy
    VJoy --> vJoyDriver
    vJoyDriver --> MSFS

    %% Связи Мониторинг
    Telemetry --> StabMonitor
    StabMonitor --> Main

    %% Связи База данных
    AirportsJSON --> AirportsDB
    AirportsDB --> ApproachDialog
    AirportReader --> ApproachDialog

    %% Связи GUI
    Main --> GUI
    ApproachDialog --> GUI
    GUI --> Main

    %% Стили
    classDef msfsClass fill:#e1f5ff,stroke:#01579b,stroke-width:2px
    classDef inputClass fill:#fff3e0,stroke:#e65100,stroke-width:2px
    classDef navClass fill:#f3e5f5,stroke:#4a148c,stroke-width:2px
    classDef controlClass fill:#e8f5e9,stroke:#1b5e20,stroke-width:2px
    classDef mainClass fill:#ffebee,stroke:#b71c1c,stroke-width:3px
    classDef adapterClass fill:#fff9c4,stroke:#f57f17,stroke-width:2px

    class MSFS,SimConnect,WASM msfsClass
    class Telemetry,AirportReader,FMSReader inputClass
    class Navigation,ILSNav,DMENav,WindCorr navClass
    class Control,Autothrottle,FlareCtrl,VJoy controlClass
    class Main,GUI mainClass
    class AircraftAdapter,WASMInterface,Profiles adapterClass
\`\`\`

---

## Диаграмма 2: Поток данных при выполнении захода

Показывает как данные движутся от MSFS через систему к управлению самолётом.

\`\`\`mermaid
flowchart LR
    subgraph "1. Источник данных"
        MSFS[Microsoft<br/>Flight Simulator]
    end

    subgraph "2. Чтение данных"
        SimConnect[SimConnect API]
        WASM[MobiFlight WASM]
    end

    subgraph "3. Телеметрия"
        Telemetry[MSFSTelemetry<br/>━━━━━━━━━━<br/>• Позиция<br/>• Скорость<br/>• Ориентация<br/>• Навигация<br/>• Погода]
        AircraftInfo[Определение<br/>типа самолёта<br/>━━━━━━━━━━<br/>• Производитель<br/>• Модель<br/>• Тип автопилота]
    end

    subgraph "4. Обработка"
        subgraph "4a. Навигация"
            ILS[ILS Navigation<br/>━━━━━━━━━━<br/>• Localizer<br/>• Glideslope<br/>• Отклонения]
            VOR[VOR/NDB<br/>Navigation<br/>━━━━━━━━━━<br/>• Курс<br/>• Расстояние<br/>• XTE]
            DME[DME Navigation<br/>━━━━━━━━━━<br/>• Дистанция<br/>• Fixes<br/>• Arc]
        end

        subgraph "4b. Коррекции"
            Wind[Wind Correction<br/>━━━━━━━━━━<br/>• Drift angle<br/>• Crab angle<br/>• Headwind/Crosswind]
            Stab[Stabilization<br/>Monitor<br/>━━━━━━━━━━<br/>• Критерии ICAO<br/>• Нарушения<br/>• Go Around]
        end

        subgraph "4c. Адаптер"
            Adapter[Aircraft Adapter<br/>━━━━━━━━━━<br/>• Профиль самолёта<br/>• Команды автопилота<br/>• L:Vars / SimConnect]
        end
    end

    subgraph "5. Принятие решений"
        Main[AutoLandSystem<br/>━━━━━━━━━━<br/>• Фаза захода<br/>• Логика управления<br/>• Координация модулей]
    end

    subgraph "6. Управление"
        subgraph "6a. Автопилот"
            Control[MSFSControl<br/>━━━━━━━━━━<br/>• Heading<br/>• Altitude<br/>• VS]
        end

        subgraph "6b. Тяга"
            AT[Autothrottle<br/>━━━━━━━━━━<br/>• PID контроллер<br/>• Целевая скорость<br/>• Коррекция]
        end

        subgraph "6c. Выравнивание"
            Flare[Flare Controller<br/>━━━━━━━━━━<br/>• Тангаж<br/>• VS reduction<br/>• Touchdown]
        end
    end

    subgraph "7. Вывод команд"
        SimConnectOut[SimConnect<br/>Commands]
        WASMOut[WASM<br/>L:Vars / Events]
        vJoy[vJoy<br/>Direct Control]
    end

    subgraph "8. Исполнение"
        MSFSOut[Microsoft<br/>Flight Simulator<br/>━━━━━━━━━━<br/>Самолёт выполняет<br/>команды]
    end

    %% Поток данных
    MSFS -->|Состояние| SimConnect
    MSFS -->|L:Vars| WASM
    
    SimConnect -->|Данные| Telemetry
    WASM -->|L:Vars| Telemetry
    
    Telemetry -->|Телеметрия| ILS
    Telemetry -->|Телеметрия| VOR
    Telemetry -->|Телеметрия| DME
    Telemetry -->|Телеметрия| Wind
    Telemetry -->|Телеметрия| Stab
    Telemetry -->|Информация| AircraftInfo
    
    AircraftInfo -->|Тип самолёта| Adapter
    
    ILS -->|Параметры захода| Main
    VOR -->|Параметры захода| Main
    DME -->|Параметры захода| Main
    Wind -->|Коррекции| Main
    Stab -->|Статус стабилизации| Main
    Adapter -->|Профиль| Main
    
    Main -->|Команды курса/высоты| Control
    Main -->|Целевая скорость| AT
    Main -->|Активация| Flare
    Main -->|Профиль| Adapter
    
    Control -->|Команды AP| SimConnectOut
    AT -->|Тяга| vJoy
    Flare -->|Управление| vJoy
    Adapter -->|Кастомные команды| WASMOut
    Adapter -->|Fallback команды| SimConnectOut
    
    SimConnectOut -->|События| MSFSOut
    WASMOut -->|L:Vars/События| MSFSOut
    vJoy -->|Прямое управление| MSFSOut
    
    MSFSOut -.->|Обратная связь| MSFS

    %% Стили
    classDef sourceClass fill:#e1f5ff,stroke:#01579b,stroke-width:2px
    classDef readClass fill:#fff3e0,stroke:#e65100,stroke-width:2px
    classDef processClass fill:#f3e5f5,stroke:#4a148c,stroke-width:2px
    classDef decisionClass fill:#ffebee,stroke:#b71c1c,stroke-width:3px
    classDef controlClass fill:#e8f5e9,stroke:#1b5e20,stroke-width:2px
    classDef outputClass fill:#fff9c4,stroke:#f57f17,stroke-width:2px

    class MSFS,MSFSOut sourceClass
    class SimConnect,WASM readClass
    class Telemetry,AircraftInfo,ILS,VOR,DME,Wind,Stab,Adapter processClass
    class Main decisionClass
    class Control,AT,Flare controlClass
    class SimConnectOut,WASMOut,vJoy outputClass
\`\`\`

---

## Диаграмма 3: Последовательность выполнения захода

Показывает порядок действий и вызовов методов при выполнении захода на посадку.

\`\`\`mermaid
sequenceDiagram
    actor User as Пользователь
    participant GUI as GUI
    participant Main as AutoLandSystem
    participant Telem as Telemetry
    participant Adapter as AircraftAdapter
    participant Nav as Navigation/ILS
    participant Wind as WindCorrection
    participant Stab as StabilizedMonitor
    participant Control as Control/Autothrottle
    participant MSFS as Microsoft FS

    %% Подключение
    User->>GUI: Нажимает "Connect"
    GUI->>Main: connect()
    Main->>Telem: connect()
    Telem->>MSFS: SimConnect.connect()
    MSFS-->>Telem: Connected
    Main->>Adapter: detect_and_configure()
    Adapter->>Telem: get_aircraft_info()
    Telem-->>Adapter: Aircraft data
    Adapter->>Adapter: Загрузка профиля
    Adapter-->>Main: Profile configured
    Main-->>GUI: Connected ✓

    %% Настройка захода
    User->>GUI: Нажимает "Start Approach"
    GUI->>GUI: Открывает ApproachDialog
    User->>GUI: Выбирает параметры
    GUI->>Main: configure_approach(config)
    Main->>Main: Сохранение конфигурации
    GUI->>Main: start_approach()
    
    %% Начало захода
    Main->>Control: set_autopilot_master(True)
    Main->>Adapter: engage_autopilot()
    Adapter->>MSFS: Команды автопилота
    Main->>Main: phase = INITIAL
    Main->>Main: Запуск execute_approach()

    %% Цикл выполнения
    loop Каждые 0.5 секунды
        Main->>Telem: get_all_data()
        Telem->>MSFS: Запрос телеметрии
        MSFS-->>Telem: Position, Speed, Attitude, Nav
        Telem-->>Main: Telemetry data

        alt ILS заход
            Main->>Nav: calculate_ils_approach(data)
            Nav->>Nav: Расчёт localizer/glideslope
        else VOR/NDB заход
            Main->>Nav: calculate_vor_approach(data)
            Nav->>Nav: Расчёт курса/расстояния
        end
        Nav-->>Main: Approach data

        Main->>Wind: apply_wind_corrections(data)
        Wind->>Wind: Расчёт drift/crab angle
        Wind-->>Main: Corrected heading/VS

        alt Фаза INITIAL
            Main->>Main: Перехват курса
            Main->>Control: set_heading_hold(corrected_heading)
            Control->>MSFS: Установка курса
            alt Курс перехвачен и DME < 15nm
                Main->>Main: phase = INTERMEDIATE
            end
        end

        alt Фаза INTERMEDIATE
            Main->>Main: Следование по курсу
            Main->>Control: set_heading_hold(corrected_heading)
            Main->>Control: set_vertical_speed(-500)
            Control->>MSFS: Команды управления
            alt Distance < 8nm и высота близка
                Main->>Main: phase = FINAL
                Main->>Control: Активация Autothrottle
            end
        end

        alt Фаза FINAL
            Main->>Stab: check_stabilization(data)
            Stab->>Stab: Проверка критериев
            alt Нарушение стабилизации
                Stab-->>Main: UNSTABLE
                Main->>Main: execute_go_around()
                Main->>Control: Full throttle + Climb
                Main->>Main: phase = IDLE
            else Стабильно
                Stab-->>Main: STABLE
                Main->>Control: Точное следование глиссаде
                Control->>MSFS: Команды управления
                alt Radio height < 50ft
                    Main->>Main: phase = LANDING
                    Main->>Control: Активация Flare
                end
            end
        end

        alt Фаза LANDING
            Main->>Control: flare_controller.update()
            Control->>Control: Увеличение тангажа
            Control->>Control: Снижение VS
            Control->>MSFS: Команды выравнивания
            alt На земле
                Main->>Main: phase = COMPLETED
                Main->>Main: stop_approach()
            end
        end

        %% Обновление GUI
        Main-->>GUI: Обновление телеметрии
        GUI-->>User: Отображение данных
    end

    %% Завершение
    Main-->>GUI: Approach completed
    GUI-->>User: Статус "COMPLETED"
\`\`\`

---

## Легенда к диаграммам

### Цвета в Диаграмме 1 (Архитектура):
- 🔵 **Голубой** - Microsoft Flight Simulator и API
- 🟠 **Оранжевый** - Модули ввода данных
- 🟣 **Фиолетовый** - Модули навигации
- 🟢 **Зелёный** - Модули управления
- 🔴 **Красный** - Главное приложение
- 🟡 **Жёлтый** - Адаптеры самолётов

### Типы связей:
- **Сплошная линия** → - Прямая зависимость / вызов
- **Пунктирная линия** -.-> - Обратная связь

### Фазы захода (Диаграмма 3):
1. **IDLE** - Ожидание
2. **INITIAL** - Перехват курса
3. **INTERMEDIATE** - Следование и снижение
4. **FINAL** - Точное следование по глиссаде
5. **LANDING** - Выравнивание и посадка
6. **COMPLETED** - Завершено

---

## Ключевые потоки данных

### 1. Телеметрия (MSFS → Система)
\`\`\`
MSFS → SimConnect → Telemetry → Main/Navigation/Control
\`\`\`

### 2. Управление (Система → MSFS)
\`\`\`
Main → Control/Autothrottle/Flare → SimConnect/vJoy → MSFS
\`\`\`

### 3. Кастомные автопилоты (через WASM)
\`\`\`
MSFS → WASM → WASMInterface → AircraftAdapter → Main
Main → AircraftAdapter → WASMInterface → WASM → MSFS
\`\`\`

### 4. Fallback (если WASM недоступен)
\`\`\`
AircraftAdapter → Control → SimConnect → MSFS
\`\`\`

---

## Примечания

1. **Все модули независимы** - можно заменять/улучшать отдельно
2. **Main.py координирует** - центральная точка управления
3. **Telemetry - единственный источник данных** - все читают через него
4. **Control - единственная точка вывода** - все команды через него (или через Adapter)
5. **Fallback на каждом уровне** - система работает даже при отказе компонентов

---

**Дата создания:** 2026-04-16  
**Автор:** Claude (Sonnet 4)  
**Версия:** 1.0
