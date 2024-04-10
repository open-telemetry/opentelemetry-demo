<?php
// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0



declare(strict_types=1);

use App\Application\Settings\Settings;
use App\Application\Settings\SettingsInterface;
use DI\ContainerBuilder;
use Psr\Log\LogLevel;

return function (ContainerBuilder $containerBuilder) {
    // Global Settings Object
    $containerBuilder->addDefinitions([
        SettingsInterface::class => function () {
            return new Settings([
                'displayErrorDetails' => true, // Should be set to false in production
                'logError'            => false,
                'logErrorDetails'     => false,
                'logger' => [
                    'name' => 'slim-app',
                    'path' => 'php://stdout',
                    'level' => LogLevel::DEBUG,
                ],
            ]);
        }
    ]);
};
